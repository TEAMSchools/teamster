select id, user_id, `type`, lower(`value`) as `value`,
from {{ source("zendesk", "user_identities") }}
