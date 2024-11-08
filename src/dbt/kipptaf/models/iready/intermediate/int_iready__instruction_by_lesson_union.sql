select
    academic_year_int,
    student_id,
    school,
    `subject`,
    lesson_id,
    lesson_name,
    lesson_objective,
    lesson_level,
    lesson_grade,
    passed_or_not_passed,
    total_time_on_lesson_min,
    completion_date,
    passed_or_not_passed_numeric,

    'Traditional' as lesson_source,
from {{ ref("stg_iready__instruction_by_lesson") }}

union all

select
    academic_year_int,
    student_id,
    school,
    `subject`,
    lesson as lesson_id,
    lesson as lesson_name,
    null as lesson_objective,
    null as lesson_level,
    null as lesson_grade,
    lesson_result as passed_or_not_passed,
    lesson_time_on_task_min,
    completion_date,
    passed_or_not_passed_numeric,

    'Pro' as lesson_source,
from {{ ref("stg_iready__instruction_by_lesson_pro") }}
