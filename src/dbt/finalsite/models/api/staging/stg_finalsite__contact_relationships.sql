select
    c.id as finalsite_enrollment_id,

    r.id as relationship_id,
    r.rel_id,
    r.rel_name,
    r.rel_type,
    r.primary as is_primary,
    r.financial as is_financial,
    r.portal_access as has_portal_access,

    c.households[safe_offset(0)].id as household_1_id,

    (
        select logical_or(ca.value.boolean_value),
        from unnest(c.custom_attributes) as ca
        where ca.field_name = 'is_parent2'
    ) as is_parent2,
from {{ source("finalsite", "contacts") }} as c
cross join unnest(c.relationships) as r
