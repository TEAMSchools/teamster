select
    c.id as finalsite_enrollment_id,

    r.id as relationship_id,
    r.rel_id,
    r.rel_name,
    r.rel_type,
    r.primary as is_primary,
    r.financial as is_financial,
    r.portal_access as has_portal_access,
    rel_offset,
from {{ source("finalsite", "contacts") }} as c
cross join unnest(c.relationships) as r
with
offset as rel_offset
