select
    calendar_id,
    school_id,
    syear,
    rollover_id,
    district_id,
    title,
    default_calendar,
    imported,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "attendance_calendars") }}
