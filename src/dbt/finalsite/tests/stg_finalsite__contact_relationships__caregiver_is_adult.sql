select
    r.finalsite_enrollment_id,
    r.rel_id,
    r.rel_type,
    c.status as related_contact_status,
    c.grade_name as related_contact_grade,
from {{ ref("stg_finalsite__contact_relationships") }} as r
inner join
    {{ ref("stg_finalsite__contacts") }} as s
    on r.finalsite_enrollment_id = s.finalsite_enrollment_id
inner join
    {{ ref("stg_finalsite__contacts") }} as c on r.rel_id = c.finalsite_enrollment_id
where
    s.status = 'enrolled'
    and s.school_year_start = {{ var("current_academic_year") }}
    and (coalesce(r.is_primary, false) or coalesce(r.is_financial, false))
    and c.status != 'not_in_workflow'
