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
    sort_order,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "student_enrollment_codes") }}
where deleted is null
