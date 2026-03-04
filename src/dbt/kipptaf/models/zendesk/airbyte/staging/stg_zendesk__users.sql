select
    id,
    `name`,
    email,
    external_id,
    organization_id,
    suspended,
    `role`,

    json_value(user_fields.secondary_location) as secondary_location,
from {{ source("zendesk", "users") }}
