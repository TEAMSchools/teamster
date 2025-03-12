select _dlt_id, ticket_id, created_at, event_type,
from {{ source("zendesk", "ticket_events") }}
