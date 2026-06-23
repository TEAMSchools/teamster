select
    id,
    grad_subject_id,
    grad_program_id,
    credits,
    sql,
    title,
    type,
    sort_order,
    grade_level_short_name,
    `language`,
    created_at,
    updated_at,
from {{ source("focus", "grad_subject_credits") }}
