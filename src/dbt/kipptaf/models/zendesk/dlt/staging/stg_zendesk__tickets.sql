select
    id,
    created_at,
    `status`,
    `subject`,
    submitter_id,
    assignee_id,
    group_id,

    /* custom fields */
    category,
    tech_tier,
    `location`,

    concat('https://teamschools.zendesk.com/agent/tickets/', id) as ticket_url,
from {{ source("zendesk", "tickets") }}
where `status` != 'deleted'
