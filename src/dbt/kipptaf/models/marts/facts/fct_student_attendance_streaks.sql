with
    enrollments as (
        select
            studentid,
            student_number,
            yearid,
            entrydate,
            exitdate,
            _dbt_source_relation,
        from {{ ref("int_powerschool__student_enrollment_union") }}
    )

select
    {{ dbt_utils.generate_surrogate_key(["st.streak_id", "st._dbt_source_relation"]) }}
    as student_attendance_streak_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "enr.student_number",
                "enr._dbt_source_relation",
                "(st.yearid + 1990)",
                "enr.entrydate",
            ]
        )
    }} as student_enrollment_key,

    st.streak_start_date as streak_start_date_key,
    st.streak_end_date as streak_end_date_key,

    st.yearid + 1990 as academic_year,
    st.att_code as attendance_code,
    st.streak_length_membership,
    st.streak_length_calendar,
from {{ ref("int_powerschool__attendance_streak") }} as st
inner join
    enrollments as enr
    on st.studentid = enr.studentid
    and st.yearid = enr.yearid
    and st.streak_start_date >= enr.entrydate
    and st.streak_start_date < enr.exitdate
    and {{ union_dataset_join_clause(left_alias="st", right_alias="enr") }}
