select
    id,
    student_id,
    staff_id,
    person_id,
    enabled,
    request_date,
    imported,
    uuid,
    created_at,
    updated_at,
from {{ source("focus", "students_join_users") }}
