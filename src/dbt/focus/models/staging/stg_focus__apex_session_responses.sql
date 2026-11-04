select
    id,
    session_id,
    question_id,
    needs_grading,
    created_at,
    updated_at,

    cast(score_actual as numeric) as score_actual,
    cast(score_max as numeric) as score_max,
from {{ source("focus", "apex_session_responses") }}
