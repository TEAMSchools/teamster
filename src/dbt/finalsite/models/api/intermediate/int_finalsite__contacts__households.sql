with
    households_normalized as (
        -- the same normalization stg_finalsite__contacts applies to its scalar
        -- address columns: Finalsite emits empty strings (not null) and
        -- mixed-case states. Blank -> null; uppercase the state code.
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

    -- address_2 is legitimately null (no apartment line), so it is not part of
    -- completeness. Everything needed to mail a letter is.
    (
        address_1 is not null
        and city is not null
        and state is not null
        and zip is not null
    ) as is_complete_address,
from households_normalized
