with
    -- Keyed on student_number, not studentid: studentid is a PowerSchool-
    -- internal id and is null for every Focus-sourced (Miami) row, so
    -- grouping on it collapses every Miami student into one meaningless
    -- aggregate row per (yearid, fte_survey) -- SQL treats null as a single
    -- group. This model is Miami-only, so every input row is Focus-sourced.
    -- studentid is carried through as max(studentid) so nothing reading the
    -- old column breaks; it stays null here since Miami has no PowerSchool
    -- studentid.
    ada_group as (
        select
            att._dbt_source_relation,
            att.student_number,
            att.yearid,

            lower(fte.name) as fte_survey,

            max(att.studentid) as studentid,

            max(att.attendancevalue) as attendancevalue,
            max(att.membershipvalue) as membershipvalue,
        from {{ ref("int_students__attendance_daily") }} as att
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as fte
            on att.yearid = fte.powerschool_year_id
            and att.calendardate between fte.start_date and fte.end_date
            and fte.type = 'FTE'
        where
            {{ extract_source_project("att") }} = 'kippmiami'
            and att.membershipvalue = 1
            and att.attendancevalue = 1
        group by att._dbt_source_relation, att.student_number, att.yearid, fte.name
    )

select
    _dbt_source_relation,
    studentid,
    student_number,
    yearid,
    if(attendancevalue_fte2 = 1.0, true, false) as is_present_fte2,
    if(membershipvalue_fte2 = 1.0, true, false) as is_enrolled_fte2,
    if(attendancevalue_fte3 = 1.0, true, false) as is_present_fte3,
    if(membershipvalue_fte3 = 1.0, true, false) as is_enrolled_fte3,
from
    ada_group pivot (
        max(attendancevalue) as attendancevalue,
        max(membershipvalue) as membershipvalue
        for fte_survey in ('fte2', 'fte3')
    )
