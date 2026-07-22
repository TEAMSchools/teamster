select *, from {{ source("kippmiami_focus", "stg_focus__attendance_calendars") }}
