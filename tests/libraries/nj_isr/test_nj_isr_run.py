from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from teamster.libraries.nj_isr.match import TRANSFER_FOLDER, Enrollment, Student
from teamster.libraries.nj_isr.models import IsrFormatError, MissingFolderError
from teamster.libraries.nj_isr.publish import PublishResult
from teamster.libraries.nj_isr.run import (
    RunPlan,
    administration_year,
    build_plan,
    missing_districts,
    summarize,
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


def test_summary_shows_the_publish_result(tmp_path):
    result = PublishResult(
        links={},
        sheets={"Newark": "https://example.test/sheet"},
        trashed=["Old file.pdf"],
        readers={"Newark": ["reader@example.test"]},
    )

    text = summarize(small_plan(tmp_path), result)

    assert "Old file.pdf" in text
    assert "https://example.test/sheet" in text
    assert "reader@example.test" in text


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


def test_administration_year_reads_the_filenames(tmp_path):
    touch(tmp_path, "2026_Spring_7325-965_ISR_SLA_Combined.pdf")
    touch(tmp_path, "2026_Spring_7325-965_Labels_SLA.pdf")

    assert administration_year(tmp_path) == 2026


def test_administration_year_stops_when_there_are_no_isr_files(tmp_path):
    touch(tmp_path, "2026_Spring_7325-965_Labels_SLA.pdf")

    with pytest.raises(IsrFormatError, match="ISR"):
        administration_year(tmp_path)
