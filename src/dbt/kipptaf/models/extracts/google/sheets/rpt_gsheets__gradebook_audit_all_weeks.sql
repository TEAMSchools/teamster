select
    academic_year,
    region,
    school_level,
    `quarter`,
    week_number_quarter,
    week_start_monday,

    max(school_week_end_date) as week_end_friday,

from {{ ref("int_students__calendar_week") }}
where
    -- summer toggle: see skill
    academic_year = {{ var("current_academic_year") }}
    and _dbt_source_project != 'kippmiami'
    and school_level != 'ES'
group by
    academic_year,
    region,
    school_level,
    `quarter`,
    week_number_quarter,
    week_start_monday
