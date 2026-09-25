with
    enrollments as (
        select
            _dbt_source_project,
            student_number,
            academic_year,
            grade_level,
            cohort,

            (academic_year + 13) - grade_level as cohort_implied,
        from {{ ref("int_students__student_enrollments") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and enroll_status = 0
            and grade_level >= 9
    )

select
    _dbt_source_project,
    student_number,
    academic_year,
    grade_level,
    cohort,
    cohort_implied,
from enrollments
where cohort > cohort_implied
