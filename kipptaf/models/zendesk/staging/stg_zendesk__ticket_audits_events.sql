select
    ta.id,
    ta.ticket_id,
    ta.created_at,

    json_value(e, '$.type') as `type`,
    json_value(e, '$.field_name') as field_name,
    json_value(e, '$.value') as `value`,
    json_value(e, '$.previous_value') as previous_value,
from {{ source("zendesk", "ticket_audits") }} as ta
cross join unnest(ta.events) as e
