select
    id,
    staff_id,
    period_id,
    course_period_id,
    school_date,
    attendance_taken_same_day,
    last_updated_date,
    created_at,
    updated_at,
from {{ source("focus", "attendance_completed") }}
