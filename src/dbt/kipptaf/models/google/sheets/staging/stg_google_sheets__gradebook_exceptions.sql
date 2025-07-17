select
    academic_year,
    region,
    school_level,
    school_id,
    quarter,
    course_number,
    section_number,
    credit_type,
    gradebook_category,
    audit_flag_name,
    is_quarter_end_date_range,
    view_name,
    cte,
    purpose,
    `include`,

    safe_cast(grade_level as int64) as grade_level,

from {{ source("google_sheets", "src_google_sheets__gradebook_exceptions") }}
