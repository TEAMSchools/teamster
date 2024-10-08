select
    _dagster_partition_academic_year as academic_year_int,
    student_id,
    academic_year,
    school,

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

    coalesce(
        student_grade.string_value, cast(student_grade.long_value as string)
    ) as student_grade,

    coalesce(cast(score.double_value as int), score.long_value) as score,
    coalesce(
        cast(total_time_on_lesson_min.double_value as int),
        total_time_on_lesson_min.long_value
    ) as total_time_on_lesson_min,

    parse_date('%m/%d/%Y', completion_date) as completion_date,

    if(passed_or_not_passed = 'Passed', 1.0, 0.0) as passed_or_not_passed_numeric,
from {{ source("iready", "src_iready__personalized_instruction_by_lesson") }}
