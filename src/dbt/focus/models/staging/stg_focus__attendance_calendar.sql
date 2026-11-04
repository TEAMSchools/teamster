select
    id,
    calendar_id,
    school_id,
    syear,
    school_date,
    block,
    fte_period,
    bell_schedule_id,
    imported,
    uuid,
    created_at,
    updated_at,

    cast(minutes as numeric) as minutes,
from {{ source("focus", "attendance_calendar") }}
