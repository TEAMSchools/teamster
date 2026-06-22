select
    subject_id,
    syear,
    school_id,
    rollover_id,
    title,
    short_name,
    imported,
    uuid,
    created_at,
    updated_at,

    custom_1 as custom_1,
from {{ source("focus", "course_subjects") }}
