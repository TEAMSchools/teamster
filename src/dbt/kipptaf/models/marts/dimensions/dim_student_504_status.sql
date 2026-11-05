with
    stints as (
        select
            student_number,
            _dbt_source_project,
            academic_year,
            entrydate,

            entrydate as effective_date_start,

            -- PowerSchool exitdate is half-open (first day AFTER stint).
            -- Subtract 1 day to get the inclusive last day so boundary-sharing
            -- stints don't produce overlapping inclusive ends in the dim.
            coalesce(
                date_sub(exitdate, interval 1 day), cast('9999-12-31' as date)
            ) as effective_date_end,
        from {{ ref("int_students__student_enrollments") }}
        -- graduates carry NULL entry/exit as a placeholder row; drop them.
        -- is_504 is NULL where Miami leaves it unset; this drops it with false.
        where is_504 and entrydate is not null
    )

select
    _dbt_source_project,

    effective_date_start as effective_date_start_key,
    effective_date_end as effective_date_end_key,

    {{
        dbt_utils.generate_surrogate_key(
            ["student_number", "_dbt_source_project", "effective_date_start"]
        )
    }} as student_504_status_key,

    {{ student_key("student_number") }} as student_key,

    {{
        student_enrollment_key(
            "student_number", "_dbt_source_project", "academic_year", "entrydate"
        )
    }} as student_enrollment_key,

    true as is_504,
    effective_date_end = '9999-12-31' as is_current,
from stints
