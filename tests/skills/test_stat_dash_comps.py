from __future__ import annotations

import importlib.util
import sys
import zipfile
from pathlib import Path
from types import ModuleType
from xml.sax.saxutils import escape

SKILL_SCRIPTS = Path(__file__).resolve().parents[2] / ".claude/skills/stat-dash/scripts"


def _load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, SKILL_SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# --- Florida ---------------------------------------------------------------

FL_STATE_HEADER = [
    "Index",
    "School Year",
    "State",
    "Subject Area",
    "Individual Assessment",
    "Indicator - 1",
    "# of Students",
    "# of Students (Level 3 and Above)",
]
FL_CITY_HEADER = (
    FL_STATE_HEADER[:3] + ["District Name", "District Number"] + (FL_STATE_HEADER[3:])
)
FL_SCHOOL_HEADER = (
    FL_CITY_HEADER[:5] + ["School Name", "School Number"] + (FL_CITY_HEADER[5:])
)
ELA3 = "03-Third - English Language Arts - FAST"


def _fl_file(folder: Path, level: str, indicator: str, rows: list[list[str]]):
    header = {
        "state": FL_STATE_HEADER,
        "city": FL_CITY_HEADER,
        "schools": FL_SCHOOL_HEADER,
    }[level]
    lines = ["\t".join(header)] + ["\t".join(r) for r in rows]
    path = folder / f"2026-09-30 {level} {indicator}.csv"
    path.write_bytes(("\n".join(lines) + "\n").encode("utf-16"))


def _state(test, indicator_value, n, prof):
    return ["1", "2025-26", "Florida", "x", test, indicator_value, n, prof]


def _city(test, indicator_value, n, prof, district="13"):
    return ["1", "2025-26", "Florida", "13-Miami-Dade", district, "x", test,
            indicator_value, n, prof]  # fmt: skip


def _school(number, test, indicator_value, n, prof):
    return ["1", "2025-26", "Florida", "13-Miami-Dade", "13", f"S-{number}",
            number, "x", test, indicator_value, n, prof]  # fmt: skip


def _by_key(rows):
    return {
        (
            r["comparison_entity"],
            r["aligned_test_code"],
            r["comparison_demographic_subgroup"],
        ): r
        for r in rows
    }


def test_fl_maps_subgroups_and_tests(tmp_path):
    fl = _load("build_fl_comps")
    _fl_file(
        tmp_path,
        "state",
        "race",
        [
            _state(ELA3, "Black", "1,000", "400"),
            _state(ELA3, "Two or More Races", "100", "50"),
            _state(ELA3, "Pacific Islander", "10", "5"),
            _state(ELA3, "Not Reported", "10", "5"),
            _state("Civics - EOC", "Black", "200", "100"),
            _state("09-Ninth - English Language Arts - FAST", "Black", "9", "9"),
            _state("Algebra 1 - EOC", "Black", "9", "9"),
            _state("06-Sixth - Science", "Black", "9", "9"),
        ],
    )
    _fl_file(tmp_path, "state", "ml", [_state(ELA3, "Current ELL", "50", "10")])
    rows = _by_key(fl.build(tmp_path, 2025, "2025-26").rows)
    assert set(rows) == {
        ("State", "ELA03", "African American"),
        ("State", "ELA03", "Other"),
        ("State", "SOC08", "African American"),
        ("State", "ELA03", "ML"),
    }
    aa = rows[("State", "ELA03", "African American")]
    assert aa["percent_proficient"] == 0.4 and aa["total_students"] == 1000
    assert aa["comparison_demographic_group"] == "Aggregate Ethnicity"
    assert aa["school_level"] == "ES" and aa["assessment_name"] == "FAST"
    soc = rows[("State", "SOC08", "African American")]
    assert (soc["assessment_name"], soc["discipline"], soc["school_level"]) == (
        "EOC",
        "Social Studies",
        "MS",
    )


def test_fl_neighborhood_schools_sum_and_drop_suppressed(tmp_path):
    fl = _load("build_fl_comps")
    _fl_file(
        tmp_path,
        "schools",
        "all",
        [
            _school("0101", ELA3, "", "60", "30"),
            _school("0521", ELA3, "", "40", "10"),
            _school("0521", "03-Third - Mathematics - FAST", "", "*", "*"),
            _school("9999", ELA3, "", "500", "500"),  # not a neighborhood school
        ],
    )
    result = fl.build(tmp_path, 2025, "2025-26")
    rows = _by_key(result.rows)
    ns = rows[("Neighborhood Schools", "ELA03", "All Students")]
    assert ns["total_students"] == 100 and ns["percent_proficient"] == 0.4
    assert ("Neighborhood Schools", "MAT03", "All Students") not in rows
    assert result.schools_found == {"0101", "0521"}


def test_fl_level_check_flags_state_not_above_city(tmp_path):
    fl = _load("build_fl_comps")
    _fl_file(tmp_path, "state", "all", [_state(ELA3, "", "100", "50")])
    _fl_file(tmp_path, "city", "all", [_city(ELA3, "", "100", "50")])
    problems = fl.build(tmp_path, 2025, "2025-26").problems
    assert any("level check failed for 'all'" in p for p in problems)


def test_fl_level_check_passes_and_flags_wrong_district(tmp_path):
    fl = _load("build_fl_comps")
    _fl_file(tmp_path, "state", "all", [_state(ELA3, "", "1000", "500")])
    _fl_file(
        tmp_path,
        "city",
        "all",
        [_city(ELA3, "", "100", "50"), _city(ELA3, "", "100", "50", "06")],
    )
    problems = fl.build(tmp_path, 2025, "2025-26").problems
    assert problems == ["2026-09-30 city all.csv: unexpected district 06"]


def test_fl_writes_headerless_tsv_and_ignores_unnamed_files(tmp_path):
    fl = _load("build_fl_comps")
    _fl_file(tmp_path, "state", "all", [_state(ELA3, "", "10", "5")])
    (tmp_path / "Build A Table.csv").write_text("whatever")
    result = fl.build(tmp_path, 2025, "2025-26")
    assert result.ignored_files == ["Build A Table.csv"]
    out = tmp_path / "out.tsv"
    fl.write_tsv(result.rows, out)
    lines = out.read_text().splitlines()
    assert lines == [
        "2025\tFAST\tSpring\tES\t3-8\tELA\tELA03\tMiami\tState\tTotal"
        "\tAll Students\t0.5\t10\tFALSE"
    ]


# --- New Jersey ------------------------------------------------------------

NJ_HEADER = [
    "County Code",
    "County Name",
    "District Code",
    "District Name",
    "School Code",
    "School Name",
    "Subgroup",
    "Subgroup Type",
    "Registered To \nTest",
    "Valid Scores",
    "L1 Percent",
    "L2 Percent",
    "L3 Percent",
    "L4 Percent",
    "L5 Percent",
]


def _write_xlsx(path: Path, rows: list[list[str]]) -> None:
    """Minimal one-sheet workbook with inline strings."""

    def col(i: int) -> str:
        s = ""
        i += 1
        while i:
            i, r = divmod(i - 1, 26)
            s = chr(65 + r) + s
        return s

    body = []
    for ri, row in enumerate(rows, start=1):
        cells = "".join(
            f'<c r="{col(ci)}{ri}" t="inlineStr"><is><t>{escape(v)}</t></is></c>'
            for ci, v in enumerate(row)
            if v != ""
        )
        body.append(f'<row r="{ri}">{cells}</row>')
    sheet = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(body)}</sheetData></worksheet>"
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("xl/worksheets/sheet1.xml", sheet)


def _nj(level, cat, value, n, l4, l5="0", l3="0", district=""):
    if level == "State":
        ids = ["State", "", "", "", "", ""]
    else:
        ids = ["07", "x", district, "x", "", "District Total"]
    return ids + [cat, value, "0", n, "0", "0", l3, l4, l5]


def _nj_file(folder: Path, code: str, rows: list[list[str]], preamble: int = 2):
    _write_xlsx(
        folder / f"{code}.xlsx",
        [["note"]] * preamble + [NJ_HEADER] + rows + [["* Data is suppressed"]],
    )


def _nj_rows(nj, folder, code):
    test = next(t for t in nj.TESTS if t.file_code == code)
    rows, problems, suppressed = nj.rows_for_test(
        test, nj.read_results(nj.find_file(folder, test)), 2024
    )
    return rows, problems, suppressed


def test_nj_reads_xlsx_and_maps_subgroups(tmp_path):
    nj = _load("build_nj_comps")
    _nj_file(
        tmp_path,
        "ELA03",
        [
            _nj("State", "Total", "All Students", "1000", "40.5", "10.2"),
            _nj(
                "State", "Race/Ethnicity", "Black or African American", "300", "20", "5"
            ),
            _nj("State", "Subgroup", "Current - Ml", "80", "10", "0"),
            _nj("State", "Subgroup", "Multilingual Learners", "120", "15", "0"),
            _nj("State", "Subgroup", "Non-Econ. Disadvantaged", "500", "50", "10"),
            _nj("State", "Gender", "Non-Binary/Undesignated", "5", "20", "0"),
            _nj("City", "Total", "All Students", "90", "20", "5", district="3570"),
            _nj("City", "Total", "All Students", "90", "99", "0", district="9999"),
        ],
        preamble=3,  # NJGPA files put the header on row 4
    )
    rows, _, _ = _nj_rows(nj, tmp_path, "ELA03")
    newark = {
        (r["comparison_entity"], r["comparison_demographic_subgroup"]): r
        for r in rows
        if r["region"] == "Newark"
    }
    assert set(newark) == {
        ("State", "All Students"),
        ("State", "African American"),
        ("State", "ML"),
        ("State", "Non Economically Disadvantaged"),
        ("City", "All Students"),
    }
    assert newark[("State", "All Students")]["percent_proficient"] == 0.507
    assert newark[("State", "All Students")]["total_students"] == 1000
    assert newark[("State", "ML")]["total_students"] == 80
    assert newark[("City", "All Students")]["percent_proficient"] == 0.25
    # State rows repeat once per NJ region
    assert sum(r["comparison_entity"] == "State" for r in rows) == 12


def test_nj_science_uses_levels_three_and_four(tmp_path):
    nj = _load("build_nj_comps")
    _nj_file(
        tmp_path,
        "SC05",
        [_nj("State", "Total", "All Students", "100", l3="20", l4="7.9", l5="")],
    )
    rows, _, _ = _nj_rows(nj, tmp_path, "SC05")
    assert rows[0]["aligned_test_code"] == "SCI05"
    assert rows[0]["assessment_name"] == "NJSLA Science"
    assert rows[0]["percent_proficient"] == 0.279


def test_nj_suppression(tmp_path):
    nj = _load("build_nj_comps")
    _nj_file(
        tmp_path,
        "ELA03",
        [
            _nj("State", "Gender", "Male", "*", "30", "10"),  # count only
            _nj("City", "Gender", "Male", "8", "*", "*", district="0680"),
        ],
    )
    rows, problems, suppressed = _nj_rows(nj, tmp_path, "ELA03")
    male = [r for r in rows if r["region"] == "Camden"]
    assert len(male) == 1 and male[0]["comparison_entity"] == "State"
    assert male[0]["percent_proficient"] == 0.4
    assert male[0]["total_students"] == ""
    assert suppressed == 1
    assert "ELA03: no District Total rows for Newark" in problems


def test_nj_alg01_splits_middle_and_high_school(tmp_path):
    nj = _load("build_nj_comps")
    _nj_file(
        tmp_path,
        "ALG01",
        [
            _nj("State", "Total", "All Students", "1000", "30", "10"),
            _nj("State", "Gender", "Female", "500", "30", "10"),
            _nj("State", "Grade", "Grade - 06", "10", "90", "5"),
            _nj("State", "Grade", "Grade - 07", "20", "80", "5"),
            _nj("State", "Grade", "Grade - 08", "300", "60", "10"),
            _nj("State", "Grade", "Grade - 09", "600", "20", "0"),
            _nj("State", "Grade", "Grade - 10", "70", "15", "0"),
        ],
    )
    rows, _, _ = _nj_rows(nj, tmp_path, "ALG01")
    newark = {
        (
            r["school_level"],
            r["grade_range_band"],
            r["comparison_demographic_group"],
            r["comparison_demographic_subgroup"],
        ): (r["percent_proficient"], r["total_students"], r["remove_row"])
        for r in rows
        if r["region"] == "Newark"
    }
    assert newark == {
        ("MS_HS", "MS_HS", "Total", "All Students"): (0.4, 1000, "TRUE"),
        ("MS_HS", "MS_HS", "Gender", "Female"): (0.4, 500, "TRUE"),
        ("MS", "3-8", "Grade", "Grade - 08"): (0.7, 300, "FALSE"),
        ("HS_09", "HS", "Grade", "Grade - 09"): (0.2, 600, "TRUE"),
        ("HS_10", "HS", "Grade", "Grade - 10"): (0.15, 70, "TRUE"),
    }


def test_nj_alg01_middle_school_can_fold_grades(tmp_path, monkeypatch):
    nj = _load("build_nj_comps")
    monkeypatch.setattr(nj, "ALG01_MS_GRADES", ("07", "08"))
    _nj_file(
        tmp_path,
        "ALG01",
        [
            _nj("State", "Grade", "Grade - 07", "100", "90", "10"),
            _nj("State", "Grade", "Grade - 08", "300", "50", "10"),
        ],
    )
    rows, _, _ = _nj_rows(nj, tmp_path, "ALG01")
    ms = [r for r in rows if r["region"] == "Newark" and r["school_level"] == "MS"]
    assert len(ms) == 1
    assert ms[0]["comparison_demographic_subgroup"] == "All Students"
    assert ms[0]["percent_proficient"] == 0.7 and ms[0]["total_students"] == 400


def test_nj_file_url():
    nj = _load("build_nj_comps")
    by_code = {t.file_code: t for t in nj.TESTS}
    assert nj.file_url(by_code["ELA03"], 2024) == (
        "https://nj.gov/education/assessment/results/reports/2425/spring/"
        "ELA03%20NJSLA%20DATA%202024-25.xlsx"
    )
    assert nj.file_url(by_code["MATGP"], 2025) == (
        "https://nj.gov/education/assessment/results/reports/2526/njgpa/"
        "MATGP%20NJGPA%20DATA%202025-26.xlsx"
    )


def test_fl_wrong_school_year_is_a_problem(tmp_path):
    fl = _load("build_fl_comps")
    _fl_file(tmp_path, "state", "all", [_state(ELA3, "", "10", "5")])
    result = fl.build(tmp_path, 2026, "2026-27")
    assert result.rows == []
    assert result.problems[0].startswith("no rows for school year 2026-27")
