with
    custom_fields as (
        select
            cf._airbyte_tickets_hashid,

            cfo.name,

            lower(regexp_replace(tf.title, r'\W', '_')) as title,
        from {{ source("zendesk", "tickets_custom_fields") }} as cf
        inner join
            {{ source("zendesk", "ticket_fields_custom_field_options") }} as cfo
            on cf.value = cfo.value
        inner join
            {{ source("zendesk", "ticket_fields") }} as tf
            on cfo._airbyte_ticket_fields_hashid = tf._airbyte_ticket_fields_hashid
    )

select _airbyte_tickets_hashid, `name`, title,
from
    custom_fields pivot (
        max(`name`) for title in (
            'category',
            'department',
            'location',
            'tech_tier',
            'assignee_to',
            'request_status',
            'vendor'
        )
    )
