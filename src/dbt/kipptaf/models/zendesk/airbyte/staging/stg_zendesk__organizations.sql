select id, `name`,
from {{ source("zendesk", "organizations") }}
where deleted_at is null
