select
    id,
    `name`,
    location_code,
    street1,
    city,
    `state`,
    postal_code,
    active,

    nullif(street2, '') as street2,
    nullif(attention, '') as attention,
from {{ source("coupa", "src_coupa__addresses") }}
