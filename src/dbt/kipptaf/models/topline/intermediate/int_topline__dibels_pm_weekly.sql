select
    cw.student_number,
    cw.academic_year,
    cw.week_start_monday,
    cw.week_end_sunday,

    dp.met_pm_round_overall_criteria,
    dp.completed_test_round_int,
from {{ ref("int_extracts__student_enrollments_weeks") }} as cw
inner join
    {{ ref("int_amplify__pm_met_criteria") }} as dp
    on cw.student_number = dp.student_number
    and cw.academic_year = dp.academic_year
    and cw.week_start_monday between dp.start_date and dp.end_date
where cw.academic_year >= {{ var("current_academic_year") - 1 }}
