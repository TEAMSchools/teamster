with
    daily as (
        select
            student_number, schoolid, academic_year, attendancevalue, membershipvalue,
        from {{ ref("int_students__attendance_daily") }}
        where
            academic_year in ({{ var("ignite_academic_years") | join(", ") }})
            and grade_level in ({{ var("ignite_grade_levels") | join(", ") }})
            and student_number is not null
    )

select
    student_number,
    academic_year,
    schoolid,

    sum(attendancevalue) as days_present,
    sum(membershipvalue) as days_enrolled,
from daily
group by student_number, academic_year, schoolid
