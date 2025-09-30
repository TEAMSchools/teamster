select
    cw.student_number,
    cw.state_studentnumber,
    cw.student_name,
    cw.academic_year,
    cw.week_start_monday,
    cw.week_end_sunday,
    cw.week_number_academic_year,
    cw.region,
    cw.school_level,
    cw.schoolid,
    cw.school,
    cw.grade_level,
    cw.gender,
    cw.ethnicity,
    cw.iep_status,
    cw.is_504,
    cw.lep_status,
    cw.gifted_and_talented,
    cw.entrydate,
    cw.exitdate,
    cw.enroll_status,

    dp.start_date as test_round_start_date,
    dp.end_date as test_round_end_date,
    dp.round_number as test_round,
    dp.completed_test_round_int,
    dp.met_pm_round_overall_criteria,
from {{ ref("int_extracts__student_enrollments_weeks") }} as cw
inner join
    {{ ref("int_amplify__pm_met_criteria") }} as dp
    on cw.student_number = dp.student_number
    and cw.academic_year = dp.academic_year
    and cw.week_start_monday between dp.start_date and dp.end_date
