select
    cw.student_number,
    cw.academic_year,
    cw.week_start_monday,
    cw.week_end_sunday,

    case
        when amp.aggregated_measure_standard_level = 'At/Above'
        then 1
        when amp.aggregated_measure_standard_level = 'Below/Well Below'
        then 0
    end as is_proficient_int,
from {{ ref("int_extracts__student_enrollments_weeks") }} as cw
inner join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on cw.academic_year = rt.academic_year
    and cw.region = rt.city
    and cw.week_start_monday between rt.start_date and rt.end_date
    and rt.type = 'LITEX'
left join
    {{ ref("int_amplify__all_assessments") }} as amp
    on cw.student_number = amp.student_number
    and cw.academic_year = amp.academic_year
    and rt.name = amp.period
    and amp.measure_name = 'Composite'
where cw.academic_year >= {{ var("current_academic_year") - 1 }} and cw.grade_level <= 8
