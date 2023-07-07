{{ config(enabled=false) }}

with
    events as (
        select
            ticket_id,
            created_at,
            json_value(e, '$.type') as `type`,
            json_value(e, '$.field_name') as field_name,
            json_value(e, '$.value') as `value`,
        from {{ source("zendesk", "src_zendesk__ticket_audits") }}
        cross join unnest(events) as e
    )

select *
from events
