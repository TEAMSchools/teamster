select student_id, subject, lesson_id, passed_or_not_passed_numeric,
from {{ ref("stg_iready__instruction_by_lesson") }}

union all

select student_id, subject, lesson as lesson_id, passed_or_not_passed_numeric,
from {{ ref("stg_iready__instruction_by_lesson_pro") }}
