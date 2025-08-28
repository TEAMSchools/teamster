select
    co.academic_year,
    co.region,
    co.school_level,
    co.schoolid,
    co.school,
    co.studentid,
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

    coalesce(sum(c.is_successful_int), 0) as successful_calls_sum,
    count(c.is_successful_int) as required_calls_count,
from {{ ref("int_extracts__student_enrollments_weeks") }} as co
left join
    {{ ref("int_topline__attendance_calls") }} as c
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
