with
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    enrollments_raw as (
        select
            student_number,
            academic_year,
            entrydate,
            exitdate,
            _dbt_source_relation,
            _dbt_source_project,
        from {{ ref("int_students__student_enrollment_union") }}
    ),

    -- Stints sharing an entrydate hash to one student_enrollment_key, so the
    -- dedupe keeps the longest. The source test
    -- int_powerschool__ps_enrollment_all__unique_student_entrydate flags them.
    -- Focus stints cannot overlap here: int_focus__student_enrollment_roster
    -- trims each stint to the day before the next one starts.
    enrollments as (
        {{
            dbt_utils.deduplicate(
                relation="enrollments_raw",
                partition_by="student_number, academic_year, entrydate, _dbt_source_project",
                order_by="exitdate desc",
            )
        }}
    )

select
    {{ dbt_utils.generate_surrogate_key(["st.streak_id", "st._dbt_source_project"]) }}
    as student_attendance_streak_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "enr.student_number",
                "enr._dbt_source_project",
                "st.academic_year",
                "enr.entrydate",
            ]
        )
    }} as student_enrollment_key,

    st.streak_start_date as streak_start_date_key,
    st.streak_end_date as streak_end_date_key,

    st.academic_year,
    st.att_code as attendance_code,
    st.streak_length_membership,
    st.streak_length_calendar,
from {{ ref("int_students__attendance_streak") }} as st
inner join
    enrollments as enr
    on st.student_number = enr.student_number
    and st.academic_year = enr.academic_year
    and st.streak_start_date >= enr.entrydate
    and st.streak_start_date < enr.exitdate
    and st._dbt_source_project = enr._dbt_source_project
