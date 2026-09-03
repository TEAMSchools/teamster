select
    _dagster_partition_academic_year as academic_year_int,
    school,
    student_grade,
    `subject`,
    `level`,
    topic,
    lesson_status,
    lesson_result,
    lesson_language,
    lesson_title,

    cast(cast(lesson_time_on_task_min as numeric) as int) as lesson_time_on_task_min,
    cast(cast(skills_completed as numeric) as int) as skills_completed,
    cast(cast(skills_successful as numeric) as int) as skills_successful,
    cast(percent_skills_successful as numeric) as percent_skills_successful,
    cast(cast(items_completed as numeric) as int) as items_completed,
    cast(cast(items_correct as numeric) as int) as items_correct,
    cast(percent_items_correct as numeric) as percent_items_correct,

    safe_cast(student_id as int) as student_id,

    parse_date('%m/%d/%Y', completion_date) as completion_date,

    if(lesson_result = 'Passed', 1.0, 0.0) as passed_or_not_passed_numeric,
from {{ source("iready", "src_iready__instruction_by_lesson_pro") }}
