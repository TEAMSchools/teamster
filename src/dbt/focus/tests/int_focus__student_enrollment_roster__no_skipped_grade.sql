with
    stints_ranked as (
        select
            student_number,
            schoolid,
            academic_year,
            grade_level,

            row_number() over (
                partition by student_number, academic_year
                order by grade_level desc, startdate desc
            ) as rn_student_year,
        from {{ ref("int_focus__student_enrollment_roster") }}
        -- no-shows share start and exit date and never held the grade
        where startdate < exitdate
    ),

    student_years as (
        select
            student_number,
            schoolid,
            academic_year,
            grade_level,

            lag(academic_year) over (
                partition by student_number order by academic_year
            ) as prior_academic_year,
            lag(grade_level) over (
                partition by student_number order by academic_year
            ) as prior_grade_level,
        from stints_ranked
        where rn_student_year = 1
    ),

    year_steps as (
        select
            *,

            academic_year - prior_academic_year as years_elapsed,
            grade_level - prior_grade_level as grades_advanced,
        from student_years
    )

select student_number, academic_year, schoolid, prior_grade_level, grade_level,
from year_steps
where years_elapsed = 1 and grades_advanced > 1 and grade_level between 9 and 12
