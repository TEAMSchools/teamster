select
    _dagster_partition_academic_year as academic_year_int,
    student_id,
    school,

    `subject`,
    `level`,
    topic,
    lesson,
    lesson_status,
    lesson_result,
    lesson_time_on_task_min,
    lesson_language,
    skills_completed,
    skills_successful,

    parse_date('%m/%d/%Y', completion_date) as completion_date,

    coalesce(
        student_grade.string_value, cast(student_grade.long_value as string)
    ) as student_grade,

    coalesce(
        percent_skills_successful.long_value, percent_skills_successful.double_value
    ) as percent_skills_successful,
from {{ source("iready", "src_iready__instruction_by_lesson_pro") }}
