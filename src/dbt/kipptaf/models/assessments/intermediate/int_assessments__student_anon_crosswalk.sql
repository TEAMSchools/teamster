with
    students as (
        select student_number,
        from {{ ref("int_extracts__student_enrollments_subjects") }}
        where
            academic_year in (
                {{ var("current_academic_year") }},
                {{ var("current_academic_year") }} - 1
            )
    )

-- grain projection: every selected column is functionally determined
-- by student_number; not a mask for upstream duplicates
select distinct
    student_number,
    {{
        dbt_utils.generate_surrogate_key(
            ["student_number", "'" ~ env_var("STUDENT_ANON_SALT", "dev_salt") ~ "'"]
        )
    }} as student_anon_id,
from students
