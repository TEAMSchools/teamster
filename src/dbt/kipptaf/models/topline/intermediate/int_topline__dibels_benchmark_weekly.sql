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
    cw.is_enrolled_week,

    rt.name as test_round,

    'ELA' as discipline,

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
    and rt.name = amp.`period`
    and amp.measure_name = 'Composite'
where cw.grade_level < 9
