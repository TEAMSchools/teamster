with
    comm_by_week as (
        select
            co.academic_year,
            co.region,
            co.school_level,
            co.schoolid,
            co.school,
            co.studentid,
            co.week_start_monday,
            co.week_end_sunday,
            co.student_number,
            co.state_studentnumber,
            co.student_name,
            co.grade_level,
            co.gender,
            co.ethnicity,
            co.iep_status,
            co.is_504,
            co.lep_status,
            co.gifted_and_talented,
            co.entrydate,
            co.exitdate,
            co.enroll_status,

            sum(c.is_successful_int) as successful_comms_sum,
            count(c.is_successful_int) as required_comms_count,
        from {{ ref("int_extracts__student_enrollments_weeks") }} as co
        left join
            {{ ref("int_topline__attendance_contacts") }} as c
            on co.student_number = c.student_number
            and co.academic_year = c.academic_year
            and c.calendardate between co.week_start_monday and co.week_end_sunday
        where co.is_enrolled_week and co.region = 'Camden' and co.academic_year = 2024
        group by
            co.academic_year,
            co.region,
            co.school_level,
            co.schoolid,
            co.school,
            co.studentid,
            co.week_start_monday,
            co.week_end_sunday,
            co.student_number,
            co.state_studentnumber,
            co.student_name,
            co.grade_level,
            co.gender,
            co.ethnicity,
            co.iep_status,
            co.is_504,
            co.lep_status,
            co.gifted_and_talented,
            co.entrydate,
            co.exitdate,
            co.enroll_status
    )

select
    academic_year,
    region,
    school_level,
    schoolid,
    school,
    studentid,
    week_start_monday,
    week_end_sunday,
    student_number,
    state_studentnumber,
    student_name,
    grade_level,
    gender,
    ethnicity,
    iep_status,
    is_504,
    lep_status,
    gifted_and_talented,
    entrydate,
    exitdate,
    enroll_status,

    sum(successful_comms_sum) over (
        partition by academic_year, student_number order by week_start_monday asc
    ) as successful_comms_sum_running,
    sum(required_comms_count) over (
        partition by academic_year, student_number order by week_start_monday asc
    ) as required_comms_count_running,
from comm_by_week
