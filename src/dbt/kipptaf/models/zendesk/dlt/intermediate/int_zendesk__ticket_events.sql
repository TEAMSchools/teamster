select
    te.ticket_id,
    te.created_at,
    te.event_type,

    ce.event_type as child_event_type,
    ce.group_id,
    ce.assignee_id,

    g.name as group_name,

    u.email as assignee_email,
from {{ ref("stg_zendesk__ticket_events") }} as te
inner join
    {{ ref("stg_zendesk__ticket_events__child_events") }} as ce
    on te._dlt_id = ce._dlt_parent_id
left join {{ ref("stg_zendesk__groups") }} as g on ce.group_id = g.id
left join {{ ref("stg_zendesk__users") }} as u on ce.assignee_id = u.id
