with
    comm_by_week as (
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

            sum(is_successful_int) as successful_comms_sum,
            count(is_successful_int) as required_comms_count,
        from {{ ref("int_topline__attendance_contacts") }}
        where is_enrolled_week and region = 'Camden' and academic_year = 2024
        group by
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
            enroll_status
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
