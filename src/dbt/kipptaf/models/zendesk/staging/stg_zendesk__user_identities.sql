select id, user_id, `primary`, `type`, lower(`value`) as `value`,
from {{ source("zendesk", "user_identities") }}
