select
    enrollment_academic_year,
    region,
    school_level,
    schoolid,
    school,
    grade_level,
    goal_granularity,
    goal_type,
    goal_name,
    goal_value,

from {{ source("google_sheets", "src_google_sheets__finalsite__goals") }}
