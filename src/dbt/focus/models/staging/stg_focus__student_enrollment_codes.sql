select
    id,
    min_syear,
    max_syear,
    district_id,
    title,
    short_name,
    type,
    profile_ids,
    gradelevels,
    grad_type,
    uuid,
    created_at,
    updated_at,

    cast(sort_order as numeric) as sort_order,
from {{ source("focus", "student_enrollment_codes") }}
where deleted is null
