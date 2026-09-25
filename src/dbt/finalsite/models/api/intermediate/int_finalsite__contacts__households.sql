with
    households_normalized as (
        select
            c.finalsite_enrollment_id,

            h.id as household_id,
            h.country,

            nullif(trim(h.address_1), '') as address_1,
            nullif(trim(h.address_2), '') as address_2,
            nullif(trim(h.city), '') as city,
            nullif(upper(trim(h.state)), '') as state,
            nullif(trim(h.zip), '') as zip,
        from {{ ref("stg_finalsite__contacts") }} as c
        cross join unnest(c.households) as h
    )

select
    finalsite_enrollment_id,
    household_id,
    address_1,
    address_2,
    city,
    state,
    zip,
    country,

    (
        address_1 is not null
        and city is not null
        and state is not null
        and zip is not null
    ) as is_complete_address,
from households_normalized
