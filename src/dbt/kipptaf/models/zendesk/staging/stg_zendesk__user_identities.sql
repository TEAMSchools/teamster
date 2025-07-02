select id, user_id, `type`, `value`, from {{ source("zendesk", "user_identities") }}
