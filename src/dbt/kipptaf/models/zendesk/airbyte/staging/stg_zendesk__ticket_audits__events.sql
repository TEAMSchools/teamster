select
    ta.id as ticket_audit_id,
    ta.created_at as ticket_audit_created_at,
    ta.ticket_id,

    json_value(e, '$.type') as event_type,
    json_value(e, '$.field_name') as event_field_name,
    json_value(e, '$.value') as event_value,
    json_value(e, '$.previous_value') as event_previous_value,
from {{ source("zendesk", "ticket_audits") }} as ta
cross join unnest(json_extract_array(ta.events)) as e
