with
    addresses as (
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

            row_number() over (
                partition by `name`, active order by id desc
            ) as rn_name_active,
        from {{ source("coupa", "src_coupa__addresses") }}
    )

select
    id,
    `name`,
    location_code,
    street1,
    city,
    `state`,
    postal_code,
    active,
    street2,
    attention,

    if(active and rn_name_active = 1, true, false) as is_current_for_name,
from addresses
