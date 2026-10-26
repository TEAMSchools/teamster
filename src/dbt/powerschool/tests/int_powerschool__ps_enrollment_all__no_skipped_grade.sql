with
    stints as (
        select
            studentid,
            student_number,
            schoolid,
            entrydate,
            grade_level,

            -- yearid is null when entrydate falls outside every term
            if(
                extract(month from entrydate) >= 7,
                extract(year from entrydate),
                extract(year from entrydate) - 1
            ) as academic_year,
        from {{ ref("int_powerschool__ps_enrollment_all") }}
        -- no-shows share entry and exit date and never held the grade
        where
            schoolid != 999999 and grade_level between 0 and 12 and entrydate < exitdate
    ),

    stints_ranked as (
        select
            *,

            row_number() over (
                partition by studentid, academic_year
                order by grade_level desc, entrydate desc
            ) as rn_student_year,
        from stints
    ),

    student_years as (
        select
            studentid,
            student_number,
            schoolid,
            academic_year,
            grade_level,

            lag(academic_year) over (
                partition by studentid order by academic_year
            ) as prior_academic_year,
            lag(grade_level) over (
                partition by studentid order by academic_year
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

select
    studentid, student_number, academic_year, schoolid, prior_grade_level, grade_level,
from year_steps
where years_elapsed = 1 and grades_advanced > 1 and grade_level between 9 and 12
