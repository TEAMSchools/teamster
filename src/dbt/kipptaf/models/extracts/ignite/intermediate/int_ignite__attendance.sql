with
    daily as (
        select
            ad.student_number,
            ad.schoolid,
            ad.academic_year,
            ad.attendancevalue,
            ad.membershipvalue,
        from {{ ref("int_students__attendance_daily") }} as ad
        inner join
            {{ ref("int_ignite__student_years") }} as sy
            on ad.student_number = sy.student_number
            and ad.academic_year = sy.academic_year
        where ad.grade_level between 9 and 12
    )

select
    student_number,
    academic_year,
    schoolid,

    sum(attendancevalue) as days_present,
    sum(membershipvalue) as days_enrolled,
from daily
group by student_number, academic_year, schoolid
