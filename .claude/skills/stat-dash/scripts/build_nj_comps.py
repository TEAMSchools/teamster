"""Build NJ comps rows for the STAT comps sheet from NJDOE assessment result files.

NJDOE posts one .xlsx per test (NJSLA ELA/Math/Science, NJGPA) with school,
``District Total`` and ``State`` rows by subgroup. This script downloads them
for a year (or reads a folder of already-downloaded files) and emits State and
City rows for Newark, Camden and Paterson. City is the host public district.

Output: paste-ready TSV, no header, in the 14-column order of the
'State Assesssment Comps Demographics' tab. A summary goes to stderr.

Usage:
    uv run python .claude/skills/stat-dash/scripts/build_nj_comps.py \
        --academic-year 2024 --download-dir .claude/scratch/nj_2425 \
        --output .claude/scratch/nj_comps_2024.tsv

Pass ``--input-dir`` instead of ``--download-dir`` to skip the download.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import urllib.error
import urllib.request
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# trunk-ignore(bandit/B405): input is an NJDOE result file, not untrusted user XML
from xml.etree import ElementTree

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

# region -> NJDOE district code of the host public district (the City comp)
CITY_DISTRICTS = {
    "Newark": "3570",  # Newark Public School District
    "Camden": "0680",  # Camden City School District
    "Paterson": "4010",  # Paterson Public School District
}
REGION_ORDER = ["Newark", "Camden", "Paterson"]

BASE_URL = "https://nj.gov/education/assessment/results/reports"


@dataclass(frozen=True)
class Test:
    file_code: str  # NJDOE file code
    code: str  # sheet aligned_test_code
    assessment_name: str
    discipline: str
    school_level: str
    grade_range_band: str
    proficient_levels: tuple[str, ...]  # performance-level columns that count
    folder: str = "spring"
    title: str = "NJSLA"


def _njsla(code: str, discipline: str, level: str, band: str) -> Test:
    return Test(code, code, "NJSLA", discipline, level, band, ("L4", "L5"))


TESTS = [
    *(_njsla(f"ELA0{g}", "ELA", "ES", "3-8") for g in (3, 4)),
    *(_njsla(f"ELA0{g}", "ELA", "MS", "3-8") for g in (5, 6, 7, 8)),
    _njsla("ELA09", "ELA", "HS", "HS"),
    *(_njsla(f"MAT0{g}", "Math", "ES", "3-8") for g in (3, 4)),
    *(_njsla(f"MAT0{g}", "Math", "MS", "3-8") for g in (5, 6, 7, 8)),
    _njsla("ALG01", "Math", "MS_HS", "MS_HS"),
    _njsla("GEO01", "Math", "HS", "HS"),
    _njsla("ALG02", "Math", "HS", "HS"),
    # NJSLA Science has four levels; proficient is Level 3 and above
    Test("SC05", "SCI05", "NJSLA Science", "Science", "MS", "3-8", ("L3", "L4")),
    Test("SC08", "SCI08", "NJSLA Science", "Science", "MS", "3-8", ("L3", "L4")),
    Test("SC11", "SCI11", "NJSLA Science", "Science", "HS", "HS", ("L3", "L4")),
    # NJGPA has two levels; Level 2 is graduation ready
    Test("ELAGP", "ELAGP", "NJGPA", "ELA", "HS", "HS", ("L2",), "njgpa", "NJGPA"),
    Test("MATGP", "MATGP", "NJGPA", "Math", "HS", "HS", ("L2",), "njgpa", "NJGPA"),
]

# NJDOE (Subgroup, Subgroup Type) -> sheet (group, subgroup). NJDOE's two
# column names are the other way round from what they hold: "Subgroup" carries
# the category and "Subgroup Type" the value. Pairs not listed are dropped:
# Non-Binary/Undesignated, Multilingual Learners (current + former) and
# Former - Ml have no sheet subgroup.
SUBGROUPS = {
    ("Total", "All Students"): ("Total", "All Students"),
    ("Race/Ethnicity", "White"): ("Aggregate Ethnicity", "White"),
    ("Race/Ethnicity", "Black or African American"): (
        "Aggregate Ethnicity",
        "African American",
    ),
    ("Race/Ethnicity", "Asian"): ("Aggregate Ethnicity", "Asian"),
    ("Race/Ethnicity", "American Indian"): ("Aggregate Ethnicity", "American Indian"),
    ("Race/Ethnicity", "Hispanic"): ("Aggregate Ethnicity", "Hispanic"),
    ("Race/Ethnicity", "Native Hawaiian"): ("Aggregate Ethnicity", "Native Hawaiian"),
    ("Race/Ethnicity", "Other"): ("Aggregate Ethnicity", "Other"),
    ("Gender", "Male"): ("Gender", "Male"),
    ("Gender", "Female"): ("Gender", "Female"),
    ("Subgroup", "Students With Disabilities"): (
        "Subgroup",
        "Students With Disabilities",
    ),
    ("Subgroup", "Current - Ml"): ("Subgroup", "ML"),
    ("Subgroup", "Economically Disadvantaged"): (
        "Subgroup",
        "Economically Disadvantaged",
    ),
    ("Subgroup", "Non-Econ. Disadvantaged"): (
        "Subgroup",
        "Non Economically Disadvantaged",
    ),
    ("Subgroup", "SE Accommodation"): ("Subgroup", "SE Accommodation"),
}

# Grade subgroups, carried for the end-of-course tests only. The sheet stores
# them as group "Grade":
# - ALG01 Grade - 08 -> school_level MS, band 3-8, remove_row FALSE. Staging
#   relabels it Total / All Students: the middle school ALG01 comparison.
# - ALG01 / GEO01 Grade - 09 and - 10 -> school_level HS_09 / HS_10, band HS,
#   remove_row TRUE. Staging rolls the ALG01 ones up into one weighted HS
#   Total / All Students row; the GEO01 ones are stored but unused.
# The ALG01 rows for all grades combined go in as MS_HS with remove_row TRUE:
# stored for reference, read by nothing.
# Grades 06 and 07 are not carried (the sheet never has); listing them in
# ALG01_MS_GRADES folds them into the MS row as a weighted Total / All Students.
ALG01_MS_GRADES = ("08",)
HS_GRADE_TESTS = ("ALG01", "GEO01")
HS_GRADES = ("09", "10")


def read_xlsx(path: Path) -> list[list[str]]:
    """Read the first worksheet of an .xlsx as rows of strings (stdlib only)."""
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as zf:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            # trunk-ignore(bandit/B314): input is an NJDOE result file, not untrusted user XML
            root = ElementTree.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", ns):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{ns['m']}}}t")))
        sheet = sorted(
            n for n in zf.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n)
        )[0]
        # trunk-ignore(bandit/B314): input is an NJDOE result file, not untrusted user XML
        root = ElementTree.fromstring(zf.read(sheet))
    rows: list[list[str]] = []
    for row in root.iter(f"{{{ns['m']}}}row"):
        cells: dict[int, str] = {}
        for c in row.findall("m:c", ns):
            col = _column_index(c.get("r", ""))
            kind = c.get("t")
            if kind == "inlineStr":
                value = "".join(t.text or "" for t in c.iter(f"{{{ns['m']}}}t"))
            else:
                v = c.find("m:v", ns)
                value = "" if v is None or v.text is None else v.text
                if kind == "s" and value:
                    value = shared[int(value)]
            cells[col if col is not None else len(cells)] = value
        width = max(cells) + 1 if cells else 0
        rows.append([cells.get(i, "") for i in range(width)])
    return rows


def _column_index(ref: str) -> int | None:
    letters = re.match(r"[A-Z]+", ref)
    if not letters:
        return None
    n = 0
    for ch in letters.group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def _clean(header: str) -> str:
    return re.sub(r"\s+", " ", header).strip()


def read_results(path: Path) -> list[dict[str, str]]:
    """Rows of an NJDOE result file, keyed by the (whitespace-normalized) header.

    The header row moves (row 3 for NJSLA, row 4 for NJGPA), so it is found by
    its first cell. Footnote rows after the table are dropped.
    """
    rows = read_xlsx(path)
    start = next(i for i, r in enumerate(rows) if r and _clean(r[0]) == "County Code")
    header = [_clean(h) for h in rows[start]]
    out = []
    for r in rows[start + 1 :]:
        rec = dict(zip(header, (v.strip() for v in r), strict=False))
        if rec.get("Subgroup Type"):
            out.append(rec)
    return out


def percent(value: str | None) -> float | None:
    value = (value or "").strip()
    if value in ("", "*"):
        return None
    return float(value)


@dataclass
class Result:
    rows: list[dict[str, object]]
    problems: list[str] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    suppressed: int = 0


def _row(year, test: Test, region, entity, level, band, group, sub, pct, n, remove):
    return {
        "academic_year": year,
        "assessment_name": test.assessment_name,
        "season": "Spring",
        "school_level": level,
        "grade_range_band": band,
        "discipline": test.discipline,
        "aligned_test_code": test.code,
        "region": region,
        "comparison_entity": entity,
        "comparison_demographic_group": group,
        "comparison_demographic_subgroup": sub,
        "percent_proficient": pct,
        "total_students": "" if n is None else n,
        "remove_row": "TRUE" if remove else "FALSE",
    }


def rows_for_test(
    test: Test, records: list[dict[str, str]], academic_year: int
) -> tuple[list[dict[str, object]], list[str], int]:
    """Comps rows for one test file, plus problems and the suppressed-cell count."""
    problems: list[str] = []
    suppressed = 0
    # entity key -> {(category, value): (percent proficient, valid scores)}
    cells: dict[tuple[str, str], dict[tuple[str, str], tuple[float, int] | None]] = (
        defaultdict(dict)
    )
    for rec in records:
        if rec.get("County Code") == "State":
            entity_key = ("State", "")
        elif (
            rec.get("School Name") == "District Total"
            and rec.get("District Code") in CITY_DISTRICTS.values()
        ):
            entity_key = ("City", rec["District Code"])
        else:
            continue
        cat, value = rec.get("Subgroup", ""), rec.get("Subgroup Type", "")
        levels = [percent(rec.get(f"{lv} Percent")) for lv in test.proficient_levels]
        n_raw = (rec.get("Valid Scores") or "").replace(",", "")
        if any(p is None for p in levels):
            cells[entity_key][(cat, value)] = None
            continue
        pct = round(sum(levels) / 100, 3)  # type: ignore[arg-type]
        # NJDOE sometimes suppresses only the count (State Female, to protect
        # a small Non-Binary cell): keep the percentage, leave the count blank.
        n = None if n_raw in ("", "*") else int(float(n_raw))
        cells[entity_key][(cat, value)] = (pct, n)

    if ("State", "") not in cells:
        problems.append(f"{test.file_code}: no State rows")
    for region, district in CITY_DISTRICTS.items():
        if ("City", district) not in cells:
            problems.append(f"{test.file_code}: no District Total rows for {region}")

    out: list[dict[str, object]] = []
    for region in REGION_ORDER:
        for entity, entity_key in (
            ("State", ("State", "")),
            ("City", ("City", CITY_DISTRICTS[region])),
        ):
            got = cells.get(entity_key, {})
            remove_all = test.code == "ALG01"
            for pair, (group, sub) in SUBGROUPS.items():
                if pair not in got:
                    continue
                if got[pair] is None:
                    suppressed += 1
                    continue
                pct, n = got[pair]  # type: ignore[misc]
                out.append(
                    _row(
                        academic_year,
                        test,
                        region,
                        entity,
                        test.school_level,
                        test.grade_range_band,
                        group,
                        sub,
                        pct,
                        n,
                        remove_all,
                    )
                )
            if test.code == "ALG01":
                ms = [got.get(("Grade", f"Grade - {g}")) for g in ALG01_MS_GRADES]
                ms = [c for c in ms if c]
                if len(ALG01_MS_GRADES) == 1 and ms:
                    pct, n = ms[0]
                    out.append(
                        _row(
                            academic_year,
                            test,
                            region,
                            entity,
                            "MS",
                            "3-8",
                            "Grade",
                            f"Grade - {ALG01_MS_GRADES[0]}",
                            pct,
                            n,
                            False,
                        )
                    )
                elif ms and all(c[1] for c in ms):
                    n = sum(c[1] for c in ms)
                    pct = round(sum(c[0] * c[1] for c in ms) / n, 3)
                    out.append(
                        _row(
                            academic_year,
                            test,
                            region,
                            entity,
                            "MS",
                            "3-8",
                            "Total",
                            "All Students",
                            pct,
                            n,
                            False,
                        )
                    )
            if test.code in HS_GRADE_TESTS:
                for g in HS_GRADES:
                    c = got.get(("Grade", f"Grade - {g}"))
                    if not c:
                        continue
                    out.append(
                        _row(
                            academic_year,
                            test,
                            region,
                            entity,
                            f"HS_{g}",
                            "HS",
                            "Grade",
                            f"Grade - {g}",
                            c[0],
                            c[1],
                            True,
                        )
                    )
    return out, problems, suppressed


def file_url(test: Test, academic_year: int) -> str:
    start, end = academic_year, academic_year + 1
    folder = f"{start % 100:02d}{end % 100:02d}"
    label = f"{start}-{end % 100:02d}"
    name = f"{test.file_code}%20{test.title}%20DATA%20{label}.xlsx"
    return f"{BASE_URL}/{folder}/{test.folder}/{name}"


def download(academic_year: int, target: Path) -> list[str]:
    """Download every test file into target; return the codes that failed."""
    target.mkdir(parents=True, exist_ok=True)
    failed = []
    for test in TESTS:
        dest = target / f"{test.file_code}.xlsx"
        if dest.exists():
            continue
        try:
            # trunk-ignore(bandit/B310): the URL is built from a fixed https base
            with urllib.request.urlopen(file_url(test, academic_year), timeout=60) as r:
                dest.write_bytes(r.read())
        except urllib.error.URLError as exc:
            failed.append(f"{test.file_code} ({exc})")
    return failed


def find_file(input_dir: Path, test: Test) -> Path | None:
    matches = sorted(input_dir.glob(f"{test.file_code}*.xlsx"))
    return matches[0] if matches else None


def build(input_dir: Path, academic_year: int) -> Result:
    result = Result(rows=[])
    for test in TESTS:
        path = find_file(input_dir, test)
        if path is None:
            result.missing_files.append(test.file_code)
            continue
        rows, problems, suppressed = rows_for_test(
            test, read_results(path), academic_year
        )
        result.rows.extend(rows)
        result.problems.extend(problems)
        result.suppressed += suppressed
    return result


def write_tsv(rows: list[dict[str, object]], output: Path) -> None:
    with output.open("w", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=COLUMNS, delimiter="\t", lineterminator="\n"
        )
        writer.writerows(rows)


def summarize(result: Result) -> str:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for r in result.rows:
        counts[(str(r["region"]), str(r["comparison_entity"]))] += 1
    lines = [f"{len(result.rows)} rows"]
    for (region, entity), n in sorted(counts.items()):
        lines.append(f"  {region} {entity}: {n}")
    lines.append(f"suppressed cells skipped: {result.suppressed}")
    if result.missing_files:
        lines.append("missing files: " + ", ".join(result.missing_files))
    for p in result.problems:
        lines.append(f"PROBLEM {p}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--academic-year",
        type=int,
        required=True,
        help="starting year: 2024 for the 2024-25 files",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input-dir", type=Path, help="folder of downloaded files")
    source.add_argument(
        "--download-dir", type=Path, help="download the files here first"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    input_dir = args.input_dir
    if args.download_dir:
        failed = download(args.academic_year, args.download_dir)
        for f in failed:
            print(f"download failed: {f}", file=sys.stderr)
        input_dir = args.download_dir

    result = build(input_dir, args.academic_year)
    write_tsv(result.rows, args.output)
    print(summarize(result), file=sys.stderr)
    print(f"wrote {args.output}", file=sys.stderr)
    return 1 if result.problems or result.missing_files else 0


if __name__ == "__main__":
    sys.exit(main())
