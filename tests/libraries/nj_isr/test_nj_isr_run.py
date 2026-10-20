import csv
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from teamster.libraries.nj_isr.match import TRANSFER_FOLDER, Enrollment, Student
from teamster.libraries.nj_isr.models import IsrFormatError, MissingFolderError
from teamster.libraries.nj_isr.publish import PublishResult
from teamster.libraries.nj_isr.run import (
    INVESTIGATION_COLUMNS,
    RunPlan,
    administration_year,
    build_plan,
    investigation_rows,
    missing_districts,
    summarize,
    write_investigation_csv,
)

TEAM = Enrollment("Newark", 133570965, "KIPP TEAM Academy")

ALEX = Student(
    student_number=101,
    last_name="Rivera",
    first_name="Alex",
    dob=date(2015, 3, 4),
    current=TEAM,
    last_spring_school="KIPP TEAM Academy",
)

SID_A = "1000000001"
SID_B = "1000000002"
XW = {SID_A: {101}, SID_B: {102}}
STUDENTS = {101: ALEX}


def touch(folder: Path, name: str) -> None:
    (folder / name).write_bytes(b"")


def _record_pages(district: str, seq: int, sid: str) -> list[str]:
    """Pages in the shape pdfium returns: CRLF endings and the name and grade on one
    line.
    """
    footer = f"{district}.{district}_965.{seq}"
    text = "\r\n".join(
        [
            "English Language Arts",
            "ALEX B. RIVERA ENROLLED GRADE: 5",
            f"Student ID: {sid} Date of Birth: 03/04/15 Date of Testing: SPRING 2026",
        ]
    )
    return [text + footer, text + footer]


def fake_pages(path: Path) -> list[str]:
    district = path.name.split("_")[2].split("-")[0]

    if path.name.endswith("_100226.pdf"):
        return _record_pages(district, 1, SID_A)

    return _record_pages(district, 1, SID_A) + _record_pages(district, 2, SID_B)


def small_plan(folder: Path) -> RunPlan:
    touch(folder, "2026_Spring_7325-965_ISR_SLA_Combined.pdf")
    touch(folder, "2026_Spring_7325-965_ISR_SLA_Combined_100226.pdf")
    return build_plan(
        folder, read_pages=fake_pages, crosswalk=XW, by_state_id={}, students=STUDENTS
    )


def three_district_plan(folder: Path, names: list[str]) -> RunPlan:
    for name in names:
        touch(folder, name)
    return build_plan(
        folder, read_pages=fake_pages, crosswalk=XW, by_state_id={}, students=STUDENTS
    )


def test_build_plan_counts(tmp_path):
    touch(tmp_path, "2026_Spring_7325-965_ISR_SLA_Combined.pdf")
    touch(tmp_path, "2026_Spring_7325-965_ISR_SLA_Combined_100226.pdf")
    touch(tmp_path, "2026_Spring_7325-965_Labels_SLA.pdf")

    plan = build_plan(
        tmp_path,
        read_pages=fake_pages,
        crosswalk=XW,
        by_state_id={},
        students=STUDENTS,
    )

    assert (plan.program, plan.admin, plan.tag, plan.school_year) == (
        "NJSLA",
        "Spring 2026",
        "2026_Spring_NJSLA",
        2026,
    )
    assert len(plan.records_in) == 3
    assert len(plan.replaced) == 1
    assert sum(len(f.entries) for f in plan.files) == 2
    assert len(plan.placements) == 2
    assert set(plan.rows_by_region) == {"Newark"}


def test_build_plan_finds_files_in_the_states_nested_folders(tmp_path):
    nested = tmp_path / "2026_Spring_7325_SLA" / "2026_Spring_7325-965_SLA"
    nested.mkdir(parents=True)
    touch(nested, "2026_Spring_7325-965_ISR_SLA_Combined.pdf")

    assert administration_year(tmp_path) == 2026

    plan = build_plan(
        tmp_path,
        read_pages=fake_pages,
        crosswalk=XW,
        by_state_id={},
        students=STUDENTS,
    )

    assert len(plan.records_in) == 2


def test_build_plan_school_year_override(tmp_path):
    touch(tmp_path, "2026_Spring_7325-965_ISR_SLA_Combined.pdf")

    plan = build_plan(
        tmp_path,
        read_pages=fake_pages,
        crosswalk=XW,
        by_state_id={},
        students=STUDENTS,
        school_year=2027,
    )

    assert plan.school_year == 2027


def test_build_plan_stops_on_mixed_programs(tmp_path):
    touch(tmp_path, "2026_Spring_7325-965_ISR_SLA_Combined.pdf")
    touch(tmp_path, "2026_Spring_7325-965_ISR_GPA.pdf")

    with pytest.raises(IsrFormatError, match="program"):
        build_plan(
            tmp_path, read_pages=fake_pages, crosswalk={}, by_state_id={}, students={}
        )


def test_build_plan_stops_on_mixed_administrations(tmp_path):
    touch(tmp_path, "2026_Spring_7325-965_ISR_SLA_Combined.pdf")
    touch(tmp_path, "2025_Spring_7325-965_ISR_SLA_Combined.pdf")

    with pytest.raises(IsrFormatError, match="administration"):
        build_plan(
            tmp_path, read_pages=fake_pages, crosswalk={}, by_state_id={}, students={}
        )


def test_build_plan_stops_when_a_school_has_no_folder_name(tmp_path):
    touch(tmp_path, "2026_Spring_7325-965_ISR_SLA_Combined.pdf")
    students = {101: replace(ALEX, current=Enrollment("Newark", 999, "New School"))}

    with pytest.raises(MissingFolderError, match="New School"):
        build_plan(
            tmp_path,
            read_pages=fake_pages,
            crosswalk=XW,
            by_state_id={},
            students=students,
        )


def test_build_plan_sends_a_student_in_an_unserved_region_to_the_transfer_folder(
    tmp_path,
):
    touch(tmp_path, "2026_Spring_7325-965_ISR_SLA_Combined.pdf")
    miami = Enrollment("Miami", 30200, "KIPP Miami School")
    students = {101: replace(ALEX, current=miami)}

    plan = build_plan(
        tmp_path,
        read_pages=fake_pages,
        crosswalk=XW,
        by_state_id={},
        students=students,
    )

    moved = next(p for p in plan.placements if p.record.state_id == SID_A)
    assert (moved.region, moved.schoolid, moved.where) == (
        "Newark",
        None,
        TRANSFER_FOLDER,
    )
    assert moved.resolution.reason == "matched"
    assert moved.resolution.student == students[101]


def publish_result(
    trashed: list[str] | None = None, orphans_kept: list[str] | None = None
) -> PublishResult:
    return PublishResult(
        links={},
        sheets={"Newark": "https://example.test/sheet"},
        trashed=trashed or [],
        readers={"Newark": ["reader@example.test"]},
        root_name="Test root",
        root_readers=["writer: team@example.test"],
        orphans_kept=orphans_kept or [],
    )


def test_summary_lists_counts_by_region_and_destination(tmp_path):
    text = summarize(small_plan(tmp_path), None)

    assert "Newark  KIPP TEAM Academy  1 records" in text
    assert "Newark  Transfer Out & Unmatched  1 records" in text
    assert "Corrections applied: 1" in text


def test_summary_lists_unmatched_records_with_their_reason(tmp_path):
    text = summarize(small_plan(tmp_path), None)

    assert "Unmatched: 1" in text
    assert "ALEX B. RIVERA" in text
    assert "no_candidate" in text
    assert "seq 2" in text


def test_summary_counts_partial_matches(tmp_path):
    plan = _plan_with(tmp_path, students={101: replace(ALEX, dob=date(2015, 3, 5))})

    text = summarize(plan, None)

    assert "Partial matches (on the investigation list): 1" in text
    assert "Unmatched: 1" in text


def test_summary_counts_no_partial_matches_for_a_full_match(tmp_path):
    text = summarize(small_plan(tmp_path), None)

    assert "Partial matches (on the investigation list): 0" in text


def test_summary_shows_the_publish_result(tmp_path):
    result = publish_result(trashed=["Old file.pdf"])

    text = summarize(small_plan(tmp_path), result)

    assert "Trashed: 1\n  Old file.pdf" in text
    assert "Files no longer produced" not in text
    assert "https://example.test/sheet" in text
    assert "reader@example.test" in text
    assert "Root folder: Test root" in text
    assert "Root folder readers: writer: team@example.test" in text


def test_summary_lists_files_kept_without_allow_trash(tmp_path):
    result = publish_result(orphans_kept=["Old file.pdf"])

    text = summarize(small_plan(tmp_path), result)

    assert (
        "Files no longer produced (kept; rerun with --allow-trash to remove): 1\n"
        "  Old file.pdf"
    ) in text
    assert "Trashed" not in text


def test_summary_maps_each_school_to_its_drive_folder(tmp_path):
    text = summarize(small_plan(tmp_path), None)

    assert "Newark  KIPP TEAM Academy -> TEAM Report Cards" in text
    assert "Transfer Out & Unmatched ->" not in text


def test_summary_without_a_result_has_no_publish_section(tmp_path):
    text = summarize(small_plan(tmp_path), None)

    assert "Trashed" not in text
    assert "Sheet" not in text


def test_missing_districts_names_every_district_without_files(tmp_path):
    plan = three_district_plan(tmp_path, ["2026_Spring_7325-965_ISR_SLA_Combined.pdf"])

    assert missing_districts(plan) == ["1799", "7899"]


def test_missing_districts_is_empty_when_every_district_has_a_file(tmp_path):
    plan = three_district_plan(
        tmp_path,
        [
            "2026_Spring_7325-965_ISR_SLA_Combined.pdf",
            "2026_Spring_1799-111_ISR_SLA_Combined.pdf",
            "2026_Spring_7899-222_ISR_SLA_Combined.pdf",
        ],
    )

    assert missing_districts(plan) == []


def test_missing_districts_ignores_a_district_with_only_a_correction_file(tmp_path):
    plan = three_district_plan(
        tmp_path,
        [
            "2026_Spring_7325-965_ISR_SLA_Combined.pdf",
            "2026_Spring_7899-222_ISR_SLA_Combined.pdf",
            "2026_Spring_1799-111_ISR_SLA_Combined_100226.pdf",
        ],
    )

    assert missing_districts(plan) == ["1799"]


def test_missing_districts_for_njgpa_needs_only_newark_and_camden(tmp_path):
    plan = three_district_plan(
        tmp_path,
        ["2026_Spring_7325-965_ISR_GPA.pdf", "2026_Spring_1799-111_ISR_GPA.pdf"],
    )

    assert plan.program == "NJGPA"
    assert missing_districts(plan) == []


def test_missing_districts_for_njsla_still_needs_paterson(tmp_path):
    plan = three_district_plan(
        tmp_path,
        [
            "2026_Spring_7325-965_ISR_SLA_Combined.pdf",
            "2026_Spring_1799-111_ISR_SLA_Combined.pdf",
        ],
    )

    assert missing_districts(plan) == ["7899"]


def test_administration_year_reads_the_filenames(tmp_path):
    touch(tmp_path, "2026_Spring_7325-965_ISR_SLA_Combined.pdf")
    touch(tmp_path, "2026_Spring_7325-965_Labels_SLA.pdf")

    assert administration_year(tmp_path) == 2026


def test_administration_year_stops_when_there_are_no_isr_files(tmp_path):
    touch(tmp_path, "2026_Spring_7325-965_Labels_SLA.pdf")

    with pytest.raises(IsrFormatError, match="ISR"):
        administration_year(tmp_path)


def _plan_with(
    folder: Path,
    *,
    students: dict[int, Student],
    crosswalk: dict[str, set[int]] | None = None,
    by_state_id: dict[str, set[int]] | None = None,
) -> RunPlan:
    touch(folder, "2026_Spring_7325-965_ISR_SLA_Combined.pdf")
    touch(folder, "2026_Spring_7325-965_ISR_SLA_Combined_100226.pdf")
    return build_plan(
        folder,
        read_pages=fake_pages,
        crosswalk=XW if crosswalk is None else crosswalk,
        by_state_id={} if by_state_id is None else by_state_id,
        students=students,
    )


def test_investigation_rows_skip_a_full_match(tmp_path):
    rows = investigation_rows(small_plan(tmp_path))

    assert [r["issue"] for r in rows] == ["no student for this state ID"]


def test_investigation_rows_list_a_partial_match_in_the_school_file(tmp_path):
    plan = _plan_with(tmp_path, students={101: replace(ALEX, dob=date(2015, 3, 5))})

    rows = investigation_rows(plan)

    assert [r["issue"] for r in rows] == [
        "birth date differs",
        "no student for this state ID",
    ]
    partial = rows[0]
    assert partial["filed_in"] == "KIPP TEAM Academy"
    assert partial["region"] == "Newark"
    entry = next(
        e for f in plan.files for e in f.entries if e.placement.record.state_id == SID_A
    )
    assert partial["page"] == str(entry.page_in_file)
    assert partial["output_file"].endswith("NJSLA Reports - Spring 2026.pdf")
    assert partial["printed_name"] == "ALEX B. RIVERA"
    assert partial["printed_birth_date"] == "2015-03-04"
    assert partial["state_id"] == SID_A
    assert partial["student_number"] == "101"
    assert partial["powerschool_last_name"] == "Rivera"
    assert partial["powerschool_first_name"] == "Alex"
    assert partial["powerschool_birth_date"] == "2015-03-05"
    assert partial["source_file"] == (
        "2026_Spring_7325-965_ISR_SLA_Combined_100226.pdf"
    )
    assert partial["source_seq"] == "1"
    assert all(isinstance(v, str) for r in rows for v in r.values())


def test_investigation_rows_name_the_last_name_difference(tmp_path):
    students = {101: replace(ALEX, last_name="Rivero")}

    rows = investigation_rows(_plan_with(tmp_path, students=students))

    assert rows[0]["issue"] == "last name differs"
    assert rows[0]["powerschool_last_name"] == "Rivero"


def test_investigation_rows_for_no_candidate_leave_the_student_columns_blank(
    tmp_path,
):
    rows = investigation_rows(small_plan(tmp_path))

    row = rows[0]
    assert row["filed_in"] == TRANSFER_FOLDER
    assert row["state_id"] == SID_B
    assert row["page"] == "1"
    for column in (
        "student_number",
        "powerschool_last_name",
        "powerschool_first_name",
        "powerschool_birth_date",
    ):
        assert row[column] == ""


def test_investigation_rows_for_failed_confirmation_show_the_candidate(tmp_path):
    students = {101: replace(ALEX, last_name="Jones", dob=date(2012, 1, 1))}

    rows = investigation_rows(_plan_with(tmp_path, students=students))

    failed = next(r for r in rows if r["state_id"] == SID_A)
    assert failed["issue"] == "name and birth date differ"
    assert failed["filed_in"] == TRANSFER_FOLDER
    assert failed["student_number"] == "101"
    assert failed["powerschool_last_name"] == "Jones"
    assert failed["powerschool_birth_date"] == "2012-01-01"


def test_investigation_rows_for_source_conflict_list_every_candidate(tmp_path):
    other = replace(ALEX, student_number=202, last_name="Jones", dob=date(2012, 1, 1))
    nobody = replace(ALEX, last_name="Nguyen", dob=date(2013, 1, 1))

    rows = investigation_rows(
        _plan_with(
            tmp_path,
            students={101: nobody, 202: other},
            crosswalk={SID_A: {101}},
            by_state_id={SID_A: {202}},
        )
    )

    conflict = next(r for r in rows if r["state_id"] == SID_A)
    assert conflict["issue"] == "state and PowerSchool point to different students"
    assert conflict["student_number"] == "101; 202"
    assert conflict["powerschool_last_name"] == ""
    assert conflict["powerschool_first_name"] == ""
    assert conflict["powerschool_birth_date"] == ""


def test_investigation_rows_are_sorted_by_region_issue_and_printed_name(tmp_path):
    plan = _plan_with(tmp_path, students={101: replace(ALEX, dob=date(2015, 3, 5))})

    rows = investigation_rows(plan)

    keys = [(r["region"], r["issue"], r["printed_name"]) for r in rows]
    assert keys == sorted(keys)


def test_write_investigation_csv_writes_the_header_and_rows(tmp_path):
    plan = _plan_with(tmp_path, students={101: replace(ALEX, dob=date(2015, 3, 5))})
    rows = investigation_rows(plan)
    path = tmp_path / "out" / "checks.csv"

    assert write_investigation_csv(rows, path) == path

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert tuple(reader.fieldnames or ()) == INVESTIGATION_COLUMNS
        assert list(reader) == rows


def test_write_investigation_csv_with_no_rows_still_writes_the_header(tmp_path):
    path = tmp_path / "checks.csv"

    write_investigation_csv([], path)

    assert path.read_text(encoding="utf-8").strip() == ",".join(INVESTIGATION_COLUMNS)
