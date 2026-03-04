select
    t.*,

    s.name as submitter_name,
    s.email as submitter_email,

    a.name as assignee_name,
    a.email as assignee_email,

    g.name as group_name,
from {{ ref("stg_zendesk__tickets") }} as t
left join {{ ref("stg_zendesk__users") }} as s on t.submitter_id = s.id
left join {{ ref("stg_zendesk__users") }} as a on t.assignee_id = a.id
left join {{ ref("stg_zendesk__groups") }} as g on t.group_id = g.id
