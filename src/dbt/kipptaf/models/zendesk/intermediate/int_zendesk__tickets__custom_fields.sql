with
    custom_fields as (
        select
            t.id as ticket_id,

            safe_cast(json_value(cf, '$.id') as int) as custom_field_id,
            nullif(json_value(cf, '$.value'), '') as custom_field_value,
        from {{ source("zendesk", "tickets") }} as t
        cross join unnest(json_extract_array(t.custom_fields)) as cf
    )

select cf.ticket_id, cf.custom_field_value, tf.title as ticket_field_title,
from custom_fields as cf
inner join {{ source("zendesk", "ticket_fields") }} as tf on cf.custom_field_id = tf.id
where cf.custom_field_value is not null
