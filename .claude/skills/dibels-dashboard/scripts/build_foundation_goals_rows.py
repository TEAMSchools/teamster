"""Turn a raw export of the T&L DIBELS goals tab into long-format rows for
`stg_google_sheets__dibels_foundation_goals`.

Reads one TSV grid per academic year, exactly as it comes back from the
Sheets API `values().get()` call on the "DIBELS" tab (tab-separated, one line
per sheet row). Handles two tab shapes:

  - single-block: Region, Grade, MOY At/Above, EOY At/Above, MOY Well Below,
    EOY Well Below  (pre-2025 tabs, All population only)
  - two-block: the same six columns twice, "ALL Students" on the left,
    "Students with IEPs" on the right, separated by one blank column
    (2025+ tabs)

Grade = "K-2" is a band-aggregate row. It is NOT emitted as its own row --
its four range cells are collapsed the same way individual-grade cells are
and carried as `grade_range_goal` on the K/1/2 rows for that region, period,
population and goal_type (mirrors the existing Grade_Range_Goal column,
which today is populated for the K-2 band only). Any OTHER hyphenated grade
token (e.g. a hypothetical "3-5" or "6-8" band) is not a known case -- it is
skipped with a loud warning rather than silently dropped, since only K-2 has
been confirmed to carry this.

Output columns, in order (matches the destination sheet's header exactly --
that header is not to be reordered to suit this script):
  academic_year, region, grade_range, grade_band, grade_level, period,
  population, grade_goal_type, grade_goal_low, grade_goal_high, grade_goal,
  grade_range_goal
`grade_range` is the cosmetic 3-way label (K-2/3-5/6-8), a pure function of
grade_level. `grade_band` is the 2-way tiering split (GK-5/G6-8) and is kept
sheet-editable on purpose -- see grade_band()'s docstring.

The min/max rule (verified against the live stg table, not guessed):
  At/Above goal_value  = LOW end of the range
  Well Below goal_value = HIGH end of the range
This holds for MOY and EOY alike -- it is goal_type-driven, not period-driven.
The same rule collapses the K-2 band range into its single grade_range_goal
value.

Usage:
    uv run python build_foundation_goals_rows.py out.tsv 2024=ay2024.tsv 2025=ay2025.tsv
"""

import re
import sys
from pathlib import Path

GRADE_MAP = {
    "K": 0,
    "0": 0,
    "1": 1,
    "2": 2,
    "3": 3,
    "4": 4,
    "5": 5,
    "6": 6,
    "7": 7,
    "8": 8,
}

# Column offsets within a block: (offset, period, goal_type)
METRIC_COLS = [
    (2, "MOY", "At/Above"),
    (3, "EOY", "At/Above"),
    (4, "MOY", "Well Below"),
    (5, "EOY", "Well Below"),
]


def grade_band(grade_level: int) -> str:
    return "GK-5" if grade_level <= 5 else "G6-8"


def grade_range(grade_level: int) -> str:
    """Cosmetic 3-way label, kept alongside grade_band's 2-way tiering split.
    Pure function of grade_level -- not a business call, so not sheet-editable
    like grade_band is."""
    if grade_level <= 2:
        return "K-2"
    if grade_level <= 5:
        return "3-5"
    return "6-8"


def parse_range(cell: str) -> tuple[float, float] | None:
    """ "62 - 66%" -> (0.62, 0.66); "53%" -> (0.53, 0.53); "n/a"/"" -> None."""
    cell = cell.strip()
    if not cell or cell.lower() == "n/a":
        return None
    nums = re.findall(r"\d+(?:\.\d+)?", cell)
    if not nums:
        return None
    if len(nums) == 1:
        low = high = float(nums[0])
    else:
        low, high = float(nums[0]), float(nums[1])
    return (low / 100, high / 100)


def goal_value_of(goal_type: str, low: float, high: float) -> float:
    return low if goal_type == "At/Above" else high


def parse_grid(path: str, academic_year: int) -> tuple[list[tuple], list[str]]:
    rows_out: list[tuple] = []
    warnings: list[str] = []

    lines = [
        ln.rstrip("\n") for ln in Path(path).read_text().splitlines() if ln.strip()
    ]
    grid = [ln.split("\t") for ln in lines]

    has_iep = any("iep" in cell.lower() for cell in grid[0])
    header_row = 1 if has_iep else 0
    data_start = header_row + 1

    blocks = [("All", 0)]
    if has_iep:
        # find the second block's start column: first non-empty cell after the
        # blank separator, on the header row
        header = grid[header_row]
        sep = next(i for i in range(6, len(header)) if header[i].strip() == "")
        iep_start = next(i for i in range(sep, len(header)) if header[i].strip() != "")
        blocks.append(("IEP", iep_start))

    data_rows = grid[data_start:]

    # Pass 1: collect the K-2 band row's collapsed value per
    # (region, population, period, goal_type) -> grade_range_goal
    band_values: dict[tuple[str, str, str, str], float] = {}
    for row in data_rows:
        for population, start in blocks:
            if start + 1 >= len(row):
                continue
            region = row[start].strip()
            grade_str = row[start + 1].strip()
            if grade_str != "K-2" or not region:
                continue
            for offset, period, goal_type in METRIC_COLS:
                col = start + offset
                if col >= len(row):
                    continue
                parsed = parse_range(row[col])
                if parsed is None:
                    continue
                low, high = parsed
                if low > high:
                    warnings.append(
                        f"{path}: {region} K-2 band {period} {goal_type} {population}: "
                        f"low {low} > high {high} in {row[col]!r} -- grade_range_goal skipped"
                    )
                    continue
                band_values[(region, population, period, goal_type)] = round(
                    goal_value_of(goal_type, low, high), 4
                )

    # Pass 2: emit individual-grade rows, attaching grade_range_goal for K/1/2.
    for line_no, row in enumerate(data_rows, start=data_start + 1):
        for population, start in blocks:
            if start + 1 >= len(row):
                continue
            region = row[start].strip()
            grade_str = row[start + 1].strip()
            if not region or not grade_str:
                continue
            if grade_str == "K-2":
                continue  # handled in pass 1, not emitted as its own row
            if "-" in grade_str:
                warnings.append(
                    f"{path}:{line_no}: unhandled band row {grade_str!r} for {region} "
                    f"{population} -- only the K-2 band is known, skipped"
                )
                continue
            if grade_str not in GRADE_MAP:
                warnings.append(
                    f"{path}:{line_no}: unrecognized grade {grade_str!r}, skipped"
                )
                continue
            grade_level = GRADE_MAP[grade_str]

            for offset, period, goal_type in METRIC_COLS:
                col = start + offset
                if col >= len(row):
                    continue
                parsed = parse_range(row[col])
                if parsed is None:
                    continue
                low, high = parsed
                if low > high:
                    warnings.append(
                        f"{path}:{line_no}: {region} grade {grade_str} {period} {goal_type} "
                        f"{population}: low {low} > high {high} in {row[col]!r} -- skipped, fix source"
                    )
                    continue
                goal_value = goal_value_of(goal_type, low, high)
                grade_range_goal = (
                    band_values.get((region, population, period, goal_type), "")
                    if grade_level in (0, 1, 2)
                    else ""
                )
                rows_out.append(
                    (
                        academic_year,
                        region,
                        grade_range(grade_level),
                        grade_band(grade_level),
                        grade_level,
                        period,
                        population,
                        goal_type,
                        round(low, 4),
                        round(high, 4),
                        round(goal_value, 4),
                        grade_range_goal,
                    )
                )

    return rows_out, warnings


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)

    out_path = Path(sys.argv[1])
    all_rows: list[tuple] = []
    all_warnings: list[str] = []

    for arg in sys.argv[2:]:
        year_str, path = arg.split("=", 1)
        rows, warnings = parse_grid(path, int(year_str))
        print(f"{path} (AY{year_str}): {len(rows)} rows, {len(warnings)} warnings")
        all_rows.extend(rows)
        all_warnings.extend(warnings)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for row in all_rows:
            f.write("\t".join(str(v) for v in row) + "\n")

    print(f"\ntotal rows: {len(all_rows)} -> {out_path}")
    if all_warnings:
        print("\n=== warnings (rows skipped, fix source and re-run if unexpected) ===")
        print("\n".join(all_warnings))


if __name__ == "__main__":
    main()
