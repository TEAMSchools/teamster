select
    ticket_id,
    assignee_updated_at,
    initially_assigned_at,
    solved_at,
    assignee_stations,
    group_stations,
    replies,
    full_resolution_time_in_minutes.business
    as full_resolution_time_in_minutes_business,
    reply_time_in_minutes.business as reply_time_in_minutes_business,
from {{ source("zendesk", "src_zendesk__ticket_metrics_archive") }}
where id not in (select id, from {{ source("zendesk", "ticket_metrics") }})
