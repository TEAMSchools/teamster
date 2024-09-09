{% set src_model = source(
    "iready", "src_iready__personalized_instruction_by_lesson"
) %}

select
    {{
        dbt_utils.star(
            from=src_model,
            except=[
                "completion_date",
                "score",
                "student_grade",
                "total_time_on_lesson_min",
            ],
        )
    }},

    cast(left(academic_year, 4) as int) as academic_year_int,

    coalesce(
        student_grade.string_value, cast(student_grade.long_value as string)
    ) as student_grade,

    coalesce(safe_cast(score.double_value as int), score.long_value) as score,
    coalesce(
        safe_cast(total_time_on_lesson_min.double_value as int),
        total_time_on_lesson_min.long_value
    ) as total_time_on_lesson_min,

    parse_date('%m/%d/%Y', completion_date) as completion_date,

    if(passed_or_not_passed = 'Passed', 1.0, 0.0) as passed_or_not_passed_numeric,
from {{ src_model }}
