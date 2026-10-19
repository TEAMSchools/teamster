from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import pytest

from teamster.libraries.nj_isr.layout import (
    admin_label,
    build_output_files,
    check_conservation,
    index_rows,
    index_sheet_name,
    report_label,
    sheet_tabs,
    shortcut_name,
    tag_value,
    year_folder_name,
)
from teamster.libraries.nj_isr.match import (
    TRANSFER_FOLDER,
    Enrollment,
    Placement,
    Resolution,
    Student,
)
from teamster.libraries.nj_isr.models import IsrFormatError, Record, SourceFile

TEAM = Enrollment("Newark", 133570965, "KIPP TEAM Academy")
RISE = Enrollment("Paterson", 777, "KIPP Paterson Rise")


def src(
    variant: str = "Combined",
    program: str = "NJSLA",
    reissue: date | None = None,
) -> SourceFile:
    return SourceFile(
        path=Path(f"2026_Spring_7325-965_ISR_{program}_{variant}.pdf"),
        year=2026,
        season="Spring",
        district="7325",
        school_code="965",
        program=program,
        variant=variant,
        reissue_date=reissue,
    )


def rec(
    seq: int = 1,
    name: str = "ADAMS AL",
    subjects: tuple[str, ...] = ("ELA", "Math"),
    reissue: date | None = None,
    not_tested: bool = False,
    grade: int | None = 5,
) -> Record:
    return Record(
        source=src(reissue=reissue),
        seq=seq,
        page_start=1 + (seq - 1) * 4,
        page_end=seq * 4,
        state_id="1000000001",
        printed_name=name,
        printed_dob=date(2015, 3, 4),
        grade=grade,
        subjects=subjects,
        not_tested=not_tested,
    )


def student(
    last: str, first: str, number: int, current: Enrollment | None = TEAM
) -> Student:
    return Student(
        student_number=number,
        last_name=last,
        first_name=first,
        dob=date(2015, 3, 4),
        current=current,
        last_spring_school="KIPP Last Spring",
    )


def at_team(
    last: str,
    first: str,
    seq: int,
    subjects: tuple[str, ...] = ("ELA", "Math"),
    reissue: date | None = None,
    not_tested: bool = False,
) -> Placement:
    s = student(last, first, 100 + seq)
    return Placement(
        rec(seq, f"{last.upper()} {first.upper()}", subjects, reissue, not_tested),
        Resolution(s, "matched"),
        TEAM.region,
        TEAM.schoolid,
        TEAM.school_name,
    )


def at_team_for(record: Record) -> Placement:
    return Placement(
        record,
        Resolution(student("Adams", "Al", 100), "matched"),
        TEAM.region,
        TEAM.schoolid,
        TEAM.school_name,
    )


def unmatched_newark(
    printed: str, seq: int = 9, reason: str = "no_candidate"
) -> Placement:
    return Placement(
        rec(seq, printed),
        Resolution(None, reason),
        "Newark",
        None,
        TRANSFER_FOLDER,
    )


def left_newark(last: str, first: str, seq: int = 8) -> Placement:
    s = student(last, first, 100 + seq, current=None)
    return Placement(
        rec(seq, f"{last.upper()} {first.upper()}"),
        Resolution(s, "matched"),
        "Newark",
        None,
        TRANSFER_FOLDER,
    )


def at_paterson_from_newark(last: str, first: str) -> Placement:
    s = student(last, first, 300, current=RISE)
    return Placement(
        rec(1, f"{last.upper()} {first.upper()}"),
        Resolution(s, "matched"),
        RISE.region,
        RISE.schoolid,
        RISE.school_name,
    )


def rows_one_team():
    files = build_output_files([at_team("Adams", "Al", 1)])
    return index_rows(files)["Newark"]


def test_names():
    assert report_label(src(variant="Combined")) == "NJSLA Reports"
    assert report_label(src(variant="Single")) == "NJSLA Science Reports"
    assert report_label(src(program="NJGPA", variant="")) == "NJGPA Reports"
    assert year_folder_name("NJSLA", "Spring 2026") == "Spring 2026 NJSLA ISRs"
    assert (
        index_sheet_name("Newark", "NJSLA", "Spring 2026")
        == "Newark NJSLA Reports Index - Spring 2026"
    )
    assert (
        shortcut_name("NJSLA", "Spring 2026")
        == "00 - Find a student's NJSLA report - Spring 2026"
    )
    assert admin_label(src()) == "Spring 2026"
    assert tag_value(src()) == "2026_Spring_NJSLA"


def test_report_label_rejects_unknown_variant():
    with pytest.raises(IsrFormatError):
        report_label(src(variant="Mystery"))


def test_build_output_files_groups_sorts_and_numbers_pages():
    files = build_output_files(
        [
            at_team("Zane", "Ava", 3),
            at_team("Adams", "Bo", 1),
            at_team("Adams", "Al", 2),
            unmatched_newark("ZED"),
        ]
    )
    team = next(f for f in files if f.schoolid == 133570965)
    assert team.file_name == "KIPP TEAM Academy - NJSLA Reports - Spring 2026.pdf"
    assert [e.placement.resolution.student.first_name for e in team.entries] == [
        "Al",
        "Bo",
        "Ava",
    ]
    assert [e.page_in_file for e in team.entries] == [1, 5, 9]
    assert team.page_count == 12
    transfer = next(f for f in files if f.schoolid is None)
    assert (
        transfer.file_name
        == "Newark Transfer Out & Unmatched - NJSLA Reports - Spring 2026.pdf"
    )


def test_build_output_files_separates_report_types():
    single = replace(rec(2, "BAKER BO"), source=src(variant="Single"))
    files = build_output_files(
        [
            at_team("Adams", "Al", 1),
            Placement(
                single,
                Resolution(student("Baker", "Bo", 102), "matched"),
                TEAM.region,
                TEAM.schoolid,
                TEAM.school_name,
            ),
        ]
    )
    assert sorted(f.file_name for f in files) == [
        "KIPP TEAM Academy - NJSLA Reports - Spring 2026.pdf",
        "KIPP TEAM Academy - NJSLA Science Reports - Spring 2026.pdf",
    ]


def test_unmatched_sort_after_matched_in_transfer_file():
    files = build_output_files(
        [unmatched_newark("AARON ABLE"), left_newark("Zane", "Ava")]
    )
    assert len(files) == 1
    t = files[0]
    assert t.entries[0].placement.resolution.student is not None
    assert t.entries[1].placement.resolution.student is None


def test_check_conservation_flags_a_lost_record():
    a, b = rec(seq=1), rec(seq=2)
    files = build_output_files([at_team_for(a)])
    with pytest.raises(IsrFormatError, match="conservation"):
        check_conservation([a, b], [], files)


def test_check_conservation_accepts_replaced_records_and_flags_extras():
    a, b = rec(seq=1), rec(seq=2)
    files = build_output_files([at_team_for(a)])
    check_conservation([a, b], [b], files)
    with pytest.raises(IsrFormatError, match="conservation"):
        check_conservation(
            [a], [], build_output_files([at_team_for(a), at_team_for(b)])
        )


def test_index_rows_one_per_subject_and_see_report():
    rows = index_rows(
        build_output_files(
            [
                at_team("Adams", "Al", 1, subjects=("ELA", "Math")),
                at_team("Baker", "Bo", 2, subjects=()),
            ]
        )
    )["Newark"]
    assert [(r.student, r.subject, r.page) for r in rows] == [
        ("Adams, Al", "ELA", 1),
        ("Adams, Al", "Math", 1),
        ("Baker, Bo", "See report", 5),
    ]


def test_index_row_fields_for_matched_student():
    row = rows_one_team()[0]
    assert row.student_number == "101"
    assert row.grade == "5"
    assert row.where == "KIPP TEAM Academy"
    assert row.last_spring_school == "KIPP Last Spring"
    assert row.file_name == "KIPP TEAM Academy - NJSLA Reports - Spring 2026.pdf"
    assert row.note == ""


def test_index_row_blank_grade():
    p = at_team("Adams", "Al", 1)
    p = replace(p, record=replace(p.record, grade=None))
    assert index_rows(build_output_files([p]))["Newark"][0].grade == ""


def test_index_row_notes():
    row = index_rows(
        build_output_files([at_team("Adams", "Al", 1, reissue=date(2026, 10, 2))])
    )["Newark"][0]
    assert row.note == "Corrected by the state on 10/2"
    row = index_rows(build_output_files([unmatched_newark("AARON ABLE")]))["Newark"][0]
    assert (row.student, row.student_number, row.note) == (
        "Able, Aaron",
        "",
        "Not matched to a KTAF student",
    )


def test_index_row_note_combinations():
    row = index_rows(
        build_output_files(
            [at_team("Adams", "Al", 1, reissue=date(2026, 10, 2), not_tested=True)]
        )
    )["Newark"][0]
    assert row.note == (
        "Corrected by the state on 10/2; Not tested in at least 1 subject - see report"
    )
    for reason in ("failed_confirmation", "source_conflict"):
        row = index_rows(
            build_output_files([unmatched_newark("AARON ABLE", reason=reason)])
        )["Newark"][0]
        assert row.note == "Needs a check by the Data team"


def test_matched_student_in_transfer_folder_has_no_reason_note():
    row = index_rows(build_output_files([left_newark("Zane", "Ava")]))["Newark"][0]
    assert row.note == ""
    assert row.where == TRANSFER_FOLDER
    assert row.student == "Zane, Ava"
    assert row.student_number == "108"


def test_unmatched_name_edge_cases():
    rows = index_rows(
        build_output_files(
            [
                unmatched_newark("MARY ANN DE LA CRUZ", seq=1),
                unmatched_newark("CHER", seq=2),
                unmatched_newark("", seq=3),
            ]
        )
    )["Newark"]
    assert {r.student for r in rows} == {
        "Cruz, Mary Ann De La",
        "Cher",
        "Unknown student",
    }


def test_cross_region_row_goes_to_destination_region():
    rows = index_rows(build_output_files([at_paterson_from_newark("Adams", "Al")]))
    assert "Paterson" in rows and "Newark" not in rows


def test_index_never_shows_dob_state_id_or_code():
    tabs = sheet_tabs(
        index_rows(build_output_files([at_team("Adams", "Al", 1)]))["Newark"],
        {},
        region="Newark",
        program="NJSLA",
        admin="Spring 2026",
        ran_at=datetime(2026, 10, 20, 9, 0),
        page_anchor=False,
    )
    cells = [c for tab in tabs.values() for row in tab for c in row]
    assert not any(
        s in c
        for c in cells
        for s in ("1000000001", "03/04/15", "2015-03-04", "a1b2c3")
    )


def test_sheet_tabs_banner_header_and_link():
    tabs = sheet_tabs(
        rows_one_team(),
        {"KIPP TEAM Academy - NJSLA Reports - Spring 2026.pdf": "https://x/view"},
        region="Newark",
        program="NJSLA",
        admin="Spring 2026",
        ran_at=datetime(2026, 10, 20, 9, 0),
        page_anchor=True,
    )
    a = tabs["All reports"]
    assert a[0] == ["Newark NJSLA reports - Spring 2026"]
    assert a[1] == [
        "1. Press Ctrl+F (Cmd+F on a Mac) and type the student's last name."
    ]
    assert a[2] == ["2. Click the blue link in that student's row."]
    assert a[3] == ["3. Go to the page number in the Page column."]
    assert a[4] == [
        "Student",
        "Student number",
        "Grade when tested",
        "Subject",
        "Where to find it",
        "School last spring",
        "Open the report",
        "Page",
        "Note",
    ]
    assert a[5][6] == '=HYPERLINK("https://x/view#page=1", "Open report")'
    assert a[5][7] == "1"
    assert tabs["About"][1] == ["Last updated", "2026-10-20 09:00"]


def test_sheet_tabs_link_without_anchor_or_url():
    kwargs = dict(
        region="Newark",
        program="NJSLA",
        admin="Spring 2026",
        ran_at=datetime(2026, 10, 20, 9, 0),
    )
    link = {"KIPP TEAM Academy - NJSLA Reports - Spring 2026.pdf": "https://x/view"}
    plain = sheet_tabs(rows_one_team(), link, page_anchor=False, **kwargs)
    assert plain["All reports"][5][6] == '=HYPERLINK("https://x/view", "Open report")'
    none = sheet_tabs(rows_one_team(), {}, page_anchor=True, **kwargs)
    assert none["All reports"][5][6] == ""


def test_sheet_tabs_about_copy():
    tabs = sheet_tabs(
        [],
        {},
        region="Newark",
        program="NJSLA",
        admin="Spring 2026",
        ran_at=datetime(2026, 10, 20, 9, 0),
        page_anchor=False,
    )
    assert tabs["About"] == [
        [
            "What this is",
            "Every Spring 2026 NJSLA Individual Student Report for Newark, one row per student per subject.",
        ],
        ["Last updated", "2026-10-20 09:00"],
        ["Can't find a report?", "Submit a ticket to the Data team."],
        [
            "Students who left KTAF",
            "Their reports are in the Transfer Out & Unmatched folder next to this Sheet.",
        ],
    ]
    assert len(tabs["All reports"]) == 5
