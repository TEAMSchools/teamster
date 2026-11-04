select
    id,
    administration_id,
    student_id,
    test_id,
    part_id,
    score_type_id,
    test_code,
    session_id,
    imported,
    uuid,
    created_at,
    updated_at,

    cast(score as numeric) as score,
from {{ source("focus", "test_history_scores") }}
