from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from teamster.libraries.nj_isr.destinations import (
    REGION_BY_DISTRICT,
    REGION_FOLDERS,
    SCHOOL_FOLDERS,
)
from teamster.libraries.nj_isr.match import (
    TRANSFER_FOLDER,
    Enrollment,
    Resolution,
    Student,
    confirm,
    last_name_matches,
    matched_on,
    place,
    resolve,
)
from teamster.libraries.nj_isr.models import Record, SourceFile

SRC = SourceFile(
    path=Path("2026_Spring_7325-965_ISR_SLA_Combined.pdf"),
    year=2026,
    season="Spring",
    district="7325",
    school_code="965",
    program="NJSLA",
    variant="Combined",
    reissue_date=None,
)

DOB = date(2014, 3, 5)


def rec(
    sid: str = "1000000001",
    name: str = "ALEX B. RIVERA",
    dob: date | None = DOB,
) -> Record:
    return Record(
        source=SRC,
        seq=1,
        page_start=1,
        page_end=2,
        state_id=sid,
        printed_name=name,
        printed_dob=dob,
        grade=5,
        subjects=("ELA", "Math"),
        not_tested=False,
    )


alex = Student(
    student_number=101,
    last_name="Rivera",
    first_name="Alex",
    dob=DOB,
    current=Enrollment("Newark", 73252, "Rise Community School"),
    last_spring_school="Rise Community School",
)
someone_else = Student(
    student_number=202,
    last_name="Jones",
    first_name="Pat",
    dob=date(2013, 1, 1),
    current=None,
    last_spring_school=None,
)
stranger = Student(
    student_number=303,
    last_name="Nguyen",
    first_name="Lee",
    dob=date(2012, 2, 2),
    current=None,
    last_spring_school=None,
)


@pytest.mark.parametrize(
    "printed, ps_last, expected",
    [
        ("SEAN P. O'NEIL", "O'Neil", True),
        ("SEAN P. O’NEIL", "O'Neil", True),
        ("ANA GARCÍA-LOPEZ", "Garcia Lopez", True),
        ("JOSE DE LA CRUZ", "De La Cruz", True),
        ("MARIA LOPEZ", "Garcia-Lopez", True),
        ("BOBBY SMITH", "Smith", True),
        ("ALEX RIVERA", "Jones", False),
        ("", "Rivera", False),
        ("ALEX RIVERA", "", False),
        ("ALEX B. RIVERA", "B", False),
    ],
)
def test_last_name_matches(printed, ps_last, expected):
    assert last_name_matches(printed, ps_last) is expected


def test_confirm_requires_dob_and_name():
    assert confirm(rec(), alex) is True
    assert confirm(rec(dob=date(2015, 3, 5)), alex) is False
    assert confirm(rec(dob=None), alex) is False
    assert confirm(rec(name="ALEX B. JONES"), alex) is False


def test_confirm_false_when_powerschool_dob_missing():
    assert confirm(rec(dob=None), replace(alex, dob=None)) is False


def test_resolve_crosswalk_confirmed():
    r = resolve(rec(), {"1000000001": {101}}, {}, {101: alex})
    assert (r.reason, r.student) == ("matched", alex)


def test_resolve_state_id_only_confirmed():
    r = resolve(rec(), {}, {"1000000001": {101}}, {101: alex})
    assert (r.reason, r.student) == ("matched", alex)


def test_matched_on_levels():
    assert matched_on(rec(dob=DOB, name="ALEX B. RIVERA"), alex) == "both"
    assert (
        matched_on(rec(dob=date(2015, 3, 5), name="ALEX B. RIVERA"), alex)
        == "last name"
    )
    assert matched_on(rec(dob=DOB, name="ALEX B. RIVERRA"), alex) == "birth date"
    assert matched_on(rec(dob=None, name="ALEX B. JONES"), alex) == ""


def test_matched_on_ignores_a_missing_birth_date_on_both_sides():
    assert (
        matched_on(rec(dob=None, name="ALEX B. JONES"), replace(alex, dob=None)) == ""
    )


def test_resolve_full_match_records_matched_on_both():
    r = resolve(rec(), {"1000000001": {101}}, {}, {101: alex})
    assert (r.reason, r.matched_on, r.candidates) == ("matched", "both", (alex,))


def test_resolve_partial_match_routes_like_a_match():
    r = resolve(
        rec(sid="1000000001", dob=date(2015, 3, 5)),
        {"1000000001": {101}},
        {},
        {101: alex},
    )
    assert (r.reason, r.student, r.matched_on) == ("matched", alex, "last name")


def test_resolve_birth_date_only_is_a_partial_match():
    r = resolve(rec(name="ALEX B. RIVERRA"), {}, {"1000000001": {101}}, {101: alex})
    assert (r.reason, r.student, r.matched_on) == ("matched", alex, "birth date")


def test_resolve_missing_printed_dob_with_matching_name_is_a_partial_match():
    r = resolve(rec(dob=None), {"1000000001": {101}}, {}, {101: alex})
    assert (r.reason, r.student, r.matched_on) == ("matched", alex, "last name")


def test_resolve_neither_check_is_failed_confirmation_with_candidates():
    r = resolve(
        rec(sid="1000000001", dob=date(2015, 3, 5), name="ALEX B. JONES"),
        {"1000000001": {101}},
        {},
        {101: alex},
    )
    assert (r.reason, r.student, r.matched_on, r.candidates) == (
        "failed_confirmation",
        None,
        "",
        (alex,),
    )


def test_resolve_agreeing_sources_confirm_once():
    r = resolve(rec(), {"1000000001": {101}}, {"1000000001": {101}}, {101: alex})
    assert (r.reason, r.student) == ("matched", alex)


def test_resolve_conflict_picks_the_one_that_confirms():
    r = resolve(
        rec(),
        {"1000000001": {101}},
        {"1000000001": {202}},
        {101: alex, 202: someone_else},
    )
    assert (r.reason, r.student) == ("matched", alex)


def test_resolve_conflict_picks_state_id_candidate_when_it_confirms():
    r = resolve(
        rec(),
        {"1000000001": {202}},
        {"1000000001": {101}},
        {101: alex, 202: someone_else},
    )
    assert r.student == alex


def test_resolve_conflict_neither_confirms():
    r = resolve(
        rec(),
        {"1000000001": {303}},
        {"1000000001": {202}},
        {303: stranger, 202: someone_else},
    )
    assert (r.reason, r.student) == ("source_conflict", None)


def test_resolve_conflict_full_beats_partial():
    # 101 matches both checks, 202 matches the last name only
    namesake = replace(someone_else, last_name="Rivera")
    r = resolve(
        rec(),
        {"1000000001": {202}},
        {"1000000001": {101}},
        {101: alex, 202: namesake},
    )
    assert (r.reason, r.student, r.matched_on) == ("matched", alex, "both")
    assert r.candidates == (alex, namesake)


def test_resolve_conflict_single_partial_wins_when_no_full():
    # 101 matches the last name only, 303 matches neither
    r = resolve(
        rec(dob=date(2015, 3, 5)),
        {"1000000001": {303}},
        {"1000000001": {101}},
        {101: alex, 303: stranger},
    )
    assert (r.reason, r.student, r.matched_on) == ("matched", alex, "last name")
    assert r.candidates == (alex, stranger)


def test_resolve_conflict_two_partials_is_source_conflict():
    # 101 matches the last name only, 202 matches the birth date only
    by_date = replace(someone_else, dob=date(2015, 3, 5))
    r = resolve(
        rec(dob=date(2015, 3, 5)),
        {"1000000001": {101}},
        {"1000000001": {202}},
        {101: alex, 202: by_date},
    )
    assert (r.reason, r.student, r.matched_on) == ("source_conflict", None, "")
    assert r.candidates == (alex, by_date)


def test_resolve_conflict_two_last_name_partials_is_source_conflict():
    twin = replace(alex, student_number=102)
    r = resolve(
        rec(dob=date(2015, 3, 5)),
        {"1000000001": {101}},
        {"1000000001": {102}},
        {101: alex, 102: twin},
    )
    assert (r.reason, r.student) == ("source_conflict", None)


def test_resolve_conflict_candidates_are_in_student_number_order():
    r = resolve(
        rec(),
        {"1000000001": {303}},
        {"1000000001": {202}},
        {303: stranger, 202: someone_else},
    )
    assert r.candidates == (someone_else, stranger)


def test_resolve_no_candidate_has_no_candidates():
    assert resolve(rec(), {}, {}, {}).candidates == ()


def test_resolve_conflict_both_confirm_is_source_conflict():
    twin = replace(alex, student_number=102)
    r = resolve(
        rec(),
        {"1000000001": {101}},
        {"1000000001": {102}},
        {101: alex, 102: twin},
    )
    assert (r.reason, r.student) == ("source_conflict", None)


def test_resolve_ambiguous_crosswalk_falls_back_to_state_id():
    r = resolve(rec(), {"1000000001": {101, 404}}, {"1000000001": {101}}, {101: alex})
    assert r.student == alex


def test_resolve_ambiguous_with_no_other_source_is_no_candidate():
    r = resolve(rec(), {"1000000001": {101, 404}}, {}, {101: alex})
    assert (r.reason, r.student) == ("no_candidate", None)


def test_resolve_no_candidate():
    assert resolve(rec(), {}, {}, {}).reason == "no_candidate"


def test_resolve_candidate_missing_from_students_is_no_candidate():
    assert resolve(rec(), {"1000000001": {101}}, {}, {}).reason == "no_candidate"


def test_place_current_school_in_another_region():
    s = replace(alex, current=Enrollment("Paterson", 2, "Paterson Prep Middle School"))
    p = place(rec(), Resolution(s, "matched"), testing_region="Newark")
    assert (p.region, p.schoolid, p.where) == (
        "Paterson",
        2,
        "Paterson Prep Middle School",
    )


def test_place_current_school_in_testing_region():
    p = place(rec(), Resolution(alex, "matched"), testing_region="Newark")
    assert (p.region, p.schoolid, p.where) == (
        "Newark",
        73252,
        "Rise Community School",
    )
    assert p.record == rec()


def test_place_not_enrolled_goes_to_testing_region_transfer():
    s = replace(alex, current=None)
    p = place(rec(), Resolution(s, "matched"), testing_region="Camden")
    assert (p.region, p.schoolid, p.where) == ("Camden", None, TRANSFER_FOLDER)


def test_place_unmatched_goes_to_transfer():
    p = place(rec(), Resolution(None, "no_candidate"), testing_region="Newark")
    assert (p.region, p.schoolid, p.where) == ("Newark", None, TRANSFER_FOLDER)


def test_school_folders_key_on_region_and_schoolid():
    assert SCHOOL_FOLDERS[("Paterson", 2)] == "Paterson Prep Middle Report Cards"
    assert SCHOOL_FOLDERS[("Newark", 133570965)] == "TEAM Report Cards"
    assert len(SCHOOL_FOLDERS) == 19
    assert all(len(k) == 2 for k in SCHOOL_FOLDERS)


def test_region_tables_agree():
    assert set(REGION_BY_DISTRICT.values()) == set(REGION_FOLDERS)
    assert {region for region, _ in SCHOOL_FOLDERS} <= set(REGION_FOLDERS)
    assert TRANSFER_FOLDER == "Transfer Out & Unmatched"
