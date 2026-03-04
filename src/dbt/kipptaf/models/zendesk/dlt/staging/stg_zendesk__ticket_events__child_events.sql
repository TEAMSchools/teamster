select _dlt_parent_id, event_type, group_id, assignee_id,
from {{ source("zendesk", "ticket_events__child_events") }}
