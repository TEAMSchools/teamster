select
    ticket_id,
    assignee_updated_at,
    initially_assigned_at,
    solved_at,
    assignee_stations,
    group_stations,
    replies,
    safe_cast(
        full_resolution_time_in_minutes.business as int
    ) as full_resolution_time_in_minutes_business,
    safe_cast(reply_time_in_minutes.business as int) as reply_time_in_minutes_business,
from {{ source("zendesk", "ticket_metrics") }}
