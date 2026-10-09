select id, question_id, standard_id, created_at, updated_at,
from {{ source("focus", "apex_question_standards") }}
