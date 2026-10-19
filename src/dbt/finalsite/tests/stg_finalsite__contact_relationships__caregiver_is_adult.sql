select
    r.finalsite_enrollment_id,
    r.rel_id,
    r.rel_type,
    c.status as related_contact_status,
    c.grade_name as related_contact_grade,
from {{ ref("stg_finalsite__contact_relationships") }} as r
inner join
    {{ ref("stg_finalsite__contacts") }} as c on r.rel_id = c.finalsite_enrollment_id
where
    (coalesce(r.is_primary, false) or coalesce(r.is_financial, false))
    and c.status != 'not_in_workflow'
