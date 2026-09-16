select id, group_id, student_id, syear, assignment_type, uuid, created_at, updated_at,
from {{ source("focus", "students_join_groups") }}
