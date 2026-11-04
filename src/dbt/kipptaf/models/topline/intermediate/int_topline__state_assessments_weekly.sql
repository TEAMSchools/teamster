with
    subject_weeks as (
        select
            student_number,
            state_studentnumber,
            academic_year,
            region,
            grade_level,
            week_start_monday,
            week_end_sunday,
            discipline,
        from {{ ref("int_extracts__student_enrollments_subjects_weeks") }}
        /* Miami FAST keeps every year; NJ state tests keep the reporting window */
        where
            region = 'Miami' or academic_year >= {{ var("current_academic_year") - 1 }}
    )

select
    cw.student_number,
    cw.academic_year,
    cw.region,
    cw.week_start_monday,
    cw.week_end_sunday,
    cw.discipline,

    rt.name as test_round,

    fl.is_proficient_int,
from subject_weeks as cw
inner join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on cw.academic_year = rt.academic_year
    and cw.region = rt.city
    and cw.week_start_monday between rt.start_date and rt.end_date
    and rt.type = 'FAST'
inner join
    {{ ref("int_assessments__state_scores") }} as fl
    on cw.state_studentnumber = fl.state_student_id
    and cw.academic_year = fl.academic_year
    and rt.name = fl.administration_period
    and cw.discipline = fl.discipline
    and fl.score_source = 'state_fl'
where cw.region = 'Miami' and cw.grade_level >= 3

union all

select
    cw.student_number,
    cw.academic_year,
    cw.region,
    cw.week_start_monday,
    cw.week_end_sunday,
    cw.discipline,

    'Spring' as test_round,

    p.is_proficient_int,
from subject_weeks as cw
inner join
    {{ ref("int_assessments__state_scores") }} as p
    on cw.state_studentnumber = p.state_student_id
    and cw.academic_year = p.academic_year
    and cw.discipline = p.discipline
    and p.score_source = 'state_nj'
where cw.region != 'Miami'
