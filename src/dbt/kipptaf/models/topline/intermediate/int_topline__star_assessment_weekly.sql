select
    cw.student_number,
    cw.academic_year,
    cw.week_start_monday,
    cw.week_end_sunday,
    cw.discipline,

    s.is_state_benchmark_proficient_int,
from {{ ref("int_extracts__student_enrollments_subjects_weeks") }} as cw
inner join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on cw.academic_year = rt.academic_year
    and cw.region = rt.city
    and cw.week_start_monday between rt.start_date and rt.end_date
    and rt.type = 'ST'
inner join
    {{ ref("stg_renlearn__star") }} as s
    on cw.student_number = s.student_display_id
    and cw.academic_year = s.academic_year
    and cw.discipline = s.star_discipline
    and rt.name = s.screening_period_window_name
    and s.rn_subject_round = 1
where cw.region = 'Miami' and cw.grade_level <= 2
