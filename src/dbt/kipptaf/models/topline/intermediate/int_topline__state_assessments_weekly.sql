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
            entrydate,
            is_enrolled_week,
        from {{ ref("int_extracts__student_enrollments_subjects_weeks") }}
        /* Miami FAST keeps every year; NJ state tests keep the reporting window */
        where
            region = 'Miami' or academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    subject_weeks_deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="subject_weeks",
                partition_by="student_number, academic_year, week_start_monday, discipline",
                order_by="is_enrolled_week desc, entrydate desc",
            )
        }}
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
from subject_weeks_deduplicate as cw
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

    p.is_proficient_int,
from subject_weeks_deduplicate as cw
inner join
    {{ ref("int_pearson__all_assessments") }} as p
    on cw.state_studentnumber = p.statestudentidentifier
    and cw.academic_year = p.academic_year
    and cw.discipline = p.discipline
where cw.region != 'Miami'
