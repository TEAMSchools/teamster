with
    miami_current_year as (
        select is_dropped_section,
        from {{ ref("int_students__course_enrollments") }}
        where
            _dbt_source_project = 'kippmiami'
            and cc_academic_year = {{ var("current_academic_year") }}
    )

select
    count(*) as total_rows,
    countif(is_dropped_section) as dropped_rows,
    countif(is_dropped_section is null) as null_rows,
    safe_divide(countif(is_dropped_section), count(*)) as dropped_rate,
from miami_current_year
having dropped_rate > 0.2 or null_rows > 0
