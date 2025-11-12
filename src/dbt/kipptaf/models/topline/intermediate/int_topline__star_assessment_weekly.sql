select
    cw.student_number,
    cw.state_studentnumber,
    cw.student_name,
    cw.academic_year,
    cw.discipline,
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

    rt.name as test_round,

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
where cw.region = 'Miami' and cw.grade_level < 3
