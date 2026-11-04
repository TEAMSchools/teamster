select
    finalsite_enrollment_id,

    r.id as relationship_id,
    r.rel_id,
    r.rel_name,
    r.rel_type,
    r.primary as is_primary,
    r.financial as is_financial,
    r.portal_access as has_portal_access,

    household_1_id,

    (
        select logical_or(ca.value.boolean_value),
        from unnest(custom_attributes) as ca
        where ca.field_name = 'is_parent2'
    ) as is_parent2,
from {{ ref("stg_finalsite__contacts") }}
cross join unnest(relationships) as r
