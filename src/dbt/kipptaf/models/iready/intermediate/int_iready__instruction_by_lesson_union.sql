select
    _dbt_source_relation,
    academic_year_int,
    student_id,
    school,
    `subject`,
    lesson_id,
    completion_date,
    passed_or_not_passed_numeric,

    'Traditional' as lesson_source,
from {{ ref("stg_iready__instruction_by_lesson") }}

union all

select
    _dbt_source_relation,
    academic_year_int,
    student_id,
    school,
    `subject`,
    lesson as lesson_id,
    completion_date,
    passed_or_not_passed_numeric,

    'Pro' as lesson_source,
from {{ ref("stg_iready__instruction_by_lesson_pro") }}
