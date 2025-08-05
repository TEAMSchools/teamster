select student_id, safe_cast(local_student_id as int) as local_student_id,
from {{ source("illuminate_public", "students") }}
