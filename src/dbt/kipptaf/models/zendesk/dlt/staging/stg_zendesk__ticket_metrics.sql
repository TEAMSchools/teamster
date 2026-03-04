select
    ticket_id,
    assignee_updated_at,
    initially_assigned_at,
    solved_at,
    assignee_stations,
    group_stations,
    replies,
    full_resolution_time_in_minutes__business,
    reply_time_in_minutes__business,
from {{ source("zendesk", "ticket_metrics") }}
