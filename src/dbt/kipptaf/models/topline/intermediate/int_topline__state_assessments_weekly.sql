select
    cw.student_number,
    cw.academic_year,
    cw.region,
    cw.week_start_monday,
    cw.week_end_sunday,
    cw.discipline,

    rt.name as test_round,

    case
        when fl.is_proficient then 1 when not fl.is_proficient then 0
    end as is_proficient_int,
from {{ ref("int_extracts__student_enrollments_subjects_weeks") }} as cw
inner join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on cw.academic_year = rt.academic_year
    and cw.region = rt.city
    and cw.week_start_monday between rt.start_date and rt.end_date
    and rt.type = 'FAST'
inner join
    {{ ref("int_fldoe__all_assessments") }} as fl
    on cw.state_studentnumber = fl.student_id
    and cw.academic_year = fl.academic_year
    and rt.name = fl.administration_window
    and cw.discipline = fl.discipline
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

    case
        when p.is_proficient then 1 when not p.is_proficient then 0
    end as is_proficient_int,
from {{ ref("int_extracts__student_enrollments_subjects_weeks") }} as cw
inner join
    {{ ref("int_pearson__all_assessments") }} as p
    on cw.state_studentnumber = p.statestudentidentifier
    and cw.academic_year = p.academic_year
    and cw.discipline = p.discipline
where
    cw.region != 'Miami' and cw.academic_year >= {{ var("current_academic_year") - 1 }}
