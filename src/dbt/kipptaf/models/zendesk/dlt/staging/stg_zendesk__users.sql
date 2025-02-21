select id, `name`, lower(email) as email, from {{ source("zendesk", "users") }}
