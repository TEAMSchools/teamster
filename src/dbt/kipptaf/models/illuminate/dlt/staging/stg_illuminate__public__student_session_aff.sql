select *, from {{ source("illuminate_public", "student_session_aff") }}
