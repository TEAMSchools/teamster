"""Build Miami comps rows for the STAT comps sheet from FLDOE Build A Table crosstabs.

Input: one folder holding the 18 crosstabs for a year, named
``<YYYY-MM-DD> <state|city|schools> <all|race|ecodis|sex|ml|swd>.csv``. The file
name is the only record of the filters used to build each crosstab, so a file
that does not match the pattern is ignored and listed in the summary.

Output: paste-ready TSV, no header, in the 14-column order of the
'State Assesssment Comps Demographics' tab. A summary goes to stderr.

State and City use FLDOE's official totals (the ``state`` and ``city`` files).
Neighborhood Schools has no official total, so it sums the school rows; a
suppressed (``*``) school cell is dropped from that sum.

Usage:
    uv run python .claude/skills/stat-dash/scripts/build_fl_comps.py \
        <input_dir> --academic-year 2025 --school-year 2025-26 \
        --output .claude/scratch/fl_comps_2025.tsv
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

COLUMNS = [
    "academic_year",
    "assessment_name",
    "season",
    "school_level",
    "grade_range_band",
    "discipline",
    "aligned_test_code",
    "region",
    "comparison_entity",
    "comparison_demographic_group",
    "comparison_demographic_subgroup",
    "percent_proficient",
    "total_students",
    "remove_row",
]

MIAMI_DADE_DISTRICT = "13"

# Miami-Dade public schools KIPP Miami compares itself against. Only Miami is
# covered: a new KTAF Florida school outside Miami needs its own list and its
# own City (county) -- ask the STAT owner before the next run.
NEIGHBORHOOD_SCHOOLS = {
    "0101": "Arcola Lake Elementary",
    "0521": "Broadmoor Elementary",
    "6031": "Brownsville Middle",
    "4491": "Henry E.S. Reeves K-8 Center",
    "2981": "Liberty City Elementary",
    "6391": "Madison Middle",
    "4501": "Poinciana Park Elementary",  # no 2025-26 data
}

# High school tests (grade 9+ FAST, Algebra 1, Geometry, Biology 1, U.S. History)
# are left out until KTAF has 2026-27 results. When they come in, pull them
# with FLDOE's Grade Enrolled filter so middle schoolers taking an EOC compare
# to middle schoolers and high schoolers to high schoolers (issue #5636). This
# switch only documents that the mapping for them does not exist yet.
INCLUDE_HIGH_SCHOOL = False

# indicator file -> (sheet group, {FLDOE value: sheet subgroup}).
# Values not listed are dropped: Pacific Islander and Not Reported have no sheet
# subgroup; Two or More Races maps to Other.
INDICATORS = {
    "all": ("Total", {"": "All Students"}),
    "race": (
        "Aggregate Ethnicity",
        {
            "American Indian": "American Indian",
            "Asian": "Asian",
            "Black": "African American",
            "Hispanic": "Hispanic",
            "Two or More Races": "Other",
            "White": "White",
        },
    ),
    "ecodis": (
        "Subgroup",
        {
            "Eco. Disadvantaged": "Economically Disadvantaged",
            "Non-Eco. Disadvantaged": "Non Economically Disadvantaged",
        },
    ),
    "sex": ("Gender", {"Female": "Female", "Male": "Male"}),
    # Current ELL Status, not English Language Learner Code
    "ml": ("Subgroup", {"Current ELL": "ML"}),
    "swd": ("Subgroup", {"SWD": "Students With Disabilities"}),
}

ENTITY = {"state": "State", "city": "City", "schools": "Neighborhood Schools"}
ENTITY_ORDER = {"State": 0, "City": 1, "Neighborhood Schools": 2}
FILE_NAME = re.compile(r"\d{4}-\d\d-\d\d (state|city|schools) (\w+)\.csv$")
GRADE_TEST = re.compile(r"(\d\d)-\w+ - (English Language Arts|Mathematics|Science)")


def assessment_meta(individual_assessment: str) -> tuple[str, str, str, int] | None:
    """Map an FLDOE Individual Assessment label to
    (assessment_name, discipline, aligned_test_code, grade), or None to skip."""
    m = GRADE_TEST.match(individual_assessment)
    if m:
        grade, subject = int(m.group(1)), m.group(2)
        if grade > 8:
            return None
        if subject == "Science":
            if grade not in (5, 8):
                return None
            return ("Science", "Science", f"SCI{grade:02d}", grade)
        if subject.startswith("English"):
            return ("FAST", "ELA", f"ELA{grade:02d}", grade)
        return ("FAST", "Math", f"MAT{grade:02d}", grade)
    if individual_assessment.startswith("Civics"):
        return ("EOC", "Social Studies", "SOC08", 8)
    return None  # Algebra 1, Geometry, Biology 1, U.S. History: see INCLUDE_HIGH_SCHOOL


def read_crosstab(path: Path) -> list[dict[str, str]]:
    """Read a Build A Table crosstab: UTF-16 tab-separated, or UTF-8 CSV/TSV."""
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = raw.decode("utf-16")
    else:
        text = raw.decode("utf-8-sig")
    delimiter = "\t" if "\t" in text.split("\n", 1)[0] else ","
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    header = [c.replace("\xa0", " ").strip() for c in rows[0]]
    return [
        dict(zip(header, (v.strip() for v in r), strict=False)) for r in rows[1:] if r
    ]


def num(value: str | None) -> int | None:
    """Parse a count cell; ``*`` (suppressed) and blank return None."""
    value = (value or "").replace(",", "")
    return None if value in ("", "*") else int(value)


@dataclass
class Result:
    rows: list[dict[str, object]]
    problems: list[str] = field(default_factory=list)
    ignored_files: list[str] = field(default_factory=list)
    schools_found: set[str] = field(default_factory=set)
    level_totals: dict[tuple[str, str], int] = field(default_factory=dict)


def build(input_dir: Path, academic_year: int, school_year: str) -> Result:
    sums: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
    problems: list[str] = []
    ignored: list[str] = []
    seen_ns: set[str] = set()
    # (level, indicator) -> students over every in-scope row, for the level check
    level_totals: dict[tuple[str, str], int] = defaultdict(int)

    for path in sorted(input_dir.iterdir()):
        m = FILE_NAME.match(path.name)
        if not m or m.group(2) not in INDICATORS:
            if path.is_file():
                ignored.append(path.name)
            continue
        level, indicator = m.groups()
        group, value_map = INDICATORS[indicator]
        rows = read_crosstab(path)
        columns = set(rows[0]) if rows else set()
        if level == "state" and "District Number" in columns:
            problems.append(
                f"{path.name}: has a District Number column; a state file "
                "should be built with District (All)"
            )
        if level == "schools" and "School Number" not in columns:
            problems.append(
                f"{path.name}: no School Number column; expand the drilldown "
                "to District and School before downloading"
            )
            continue
        if level == "city" and "School Number" in columns:
            problems.append(
                f"{path.name}: has a School Number column; collapse the "
                "drilldown for the city file"
            )
            continue

        for r in rows:
            if r.get("School Year") != school_year:
                continue
            if level == "city" and r.get("District Number") != MIAMI_DADE_DISTRICT:
                problems.append(
                    f"{path.name}: unexpected district {r.get('District Number')}"
                )
                continue
            if level == "schools":
                if (
                    r.get("District Number") != MIAMI_DADE_DISTRICT
                    or r.get("School Number") not in NEIGHBORHOOD_SCHOOLS
                ):
                    continue
                seen_ns.add(r["School Number"])
            meta = assessment_meta(r.get("Individual Assessment", ""))
            if meta is None:
                continue
            subgroup = value_map.get(r.get("Indicator - 1", ""))
            if subgroup is None:
                continue
            n = num(r.get("# of Students"))
            prof = num(r.get("# of Students (Level 3 and Above)"))
            if n is None or prof is None:
                continue  # suppressed
            level_totals[(level, indicator)] += n
            key = (level, meta, group, subgroup)
            sums[key][0] += n
            sums[key][1] += prof

    if not sums:
        problems.append(
            f"no rows for school year {school_year}: check the file names "
            "and --school-year"
        )

    # A state file filtered to Miami-Dade, or a city file left at District (All),
    # shows up as state totals that do not exceed city totals.
    for indicator in INDICATORS:
        state_n = level_totals.get(("state", indicator))
        city_n = level_totals.get(("city", indicator))
        if state_n is not None and city_n is not None and state_n <= city_n:
            problems.append(
                f"level check failed for '{indicator}': state students "
                f"{state_n:,} do not exceed city students {city_n:,}; one of "
                "the two files was downloaded at the wrong level"
            )

    out: list[dict[str, object]] = []
    for (level, meta, group, subgroup), (n, prof) in sums.items():
        assessment, discipline, code, grade = meta
        out.append(
            {
                "academic_year": academic_year,
                "assessment_name": assessment,
                "season": "Spring",
                "school_level": "ES" if grade <= 4 else "MS",
                "grade_range_band": "3-8",
                "discipline": discipline,
                "aligned_test_code": code,
                "region": "Miami",
                "comparison_entity": ENTITY[level],
                "comparison_demographic_group": group,
                "comparison_demographic_subgroup": subgroup,
                "percent_proficient": round(prof / n, 3),
                "total_students": n,
                "remove_row": "FALSE",
            }
        )
    out.sort(
        key=lambda r: (
            r["aligned_test_code"],
            ENTITY_ORDER[str(r["comparison_entity"])],
            r["comparison_demographic_group"],
            r["comparison_demographic_subgroup"],
        )
    )
    return Result(out, problems, ignored, seen_ns, dict(level_totals))


def write_tsv(rows: list[dict[str, object]], output: Path) -> None:
    with output.open("w", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=COLUMNS, delimiter="\t", lineterminator="\n"
        )
        writer.writerows(rows)


def summarize(result: Result) -> str:
    lines = [f"{len(result.rows)} rows"]
    by_entity: dict[str, int] = defaultdict(int)
    for r in result.rows:
        by_entity[str(r["comparison_entity"])] += 1
    for entity in sorted(by_entity, key=ENTITY_ORDER.get):
        lines.append(f"  {entity}: {by_entity[entity]}")
    missing = sorted(set(NEIGHBORHOOD_SCHOOLS) - result.schools_found)
    lines.append(
        "neighborhood schools missing: "
        + (", ".join(f"{c} {NEIGHBORHOOD_SCHOOLS[c]}" for c in missing) or "none")
    )
    if result.ignored_files:
        lines.append("ignored files: " + ", ".join(result.ignored_files))
    for p in result.problems:
        lines.append(f"PROBLEM {p}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("input_dir", type=Path)
    parser.add_argument(
        "--academic-year",
        type=int,
        required=True,
        help="starting year: 2025 for the 2025-26 school year",
    )
    parser.add_argument(
        "--school-year",
        required=True,
        help="FLDOE School Year label, e.g. 2025-26",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    result = build(args.input_dir, args.academic_year, args.school_year)
    write_tsv(result.rows, args.output)
    print(summarize(result), file=sys.stderr)
    print(f"wrote {args.output}", file=sys.stderr)
    return 1 if result.problems else 0


if __name__ == "__main__":
    sys.exit(main())
