select id, apex_assignment_id, gradebook_assignment_id, created_at, updated_at,
from {{ source("focus", "apex_assignment_gradebook_assignment") }}
