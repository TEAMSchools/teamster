select
    id,
    primary_student_id,
    secondary_student_id,
    relationship,
    sync_addresses,
    sync_contacts,
    imported,
    created_at,
    updated_at,
from {{ source("focus", "students_join_students") }}
