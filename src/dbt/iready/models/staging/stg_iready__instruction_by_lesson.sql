select
    _dagster_partition_academic_year as academic_year_int,
    academic_year,
    school,
    student_grade,
    `subject`,
    domain,
    lesson_grade,
    lesson_level,
    lesson_id,
    lesson_name,
    lesson_objective,
    lesson_language,
    passed_or_not_passed,
    teacher_assigned_lesson,

    cast(student_id as int) as student_id,
    cast(score as int) as score,
    cast(total_time_on_lesson_min as int) as total_time_on_lesson_min,

    parse_date('%m/%d/%Y', completion_date) as completion_date,

    if(passed_or_not_passed = 'Passed', 1.0, 0.0) as passed_or_not_passed_numeric,
from {{ source("iready", "src_iready__instruction_by_lesson") }}
