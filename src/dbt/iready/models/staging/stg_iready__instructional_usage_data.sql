{%- set src_model = source("iready", "src_iready__instructional_usage_data") -%}

select
    {{
        dbt_utils.star(
            from=src_model,
            except=[
                "last_week_start_date",
                "last_week_end_date",
                "first_lesson_completion_date",
                "most_recent_lesson_completion_date",
                "student_grade",
            ],
        )
    }},

    safe_cast(left(academic_year, 4) as int) as academic_year_int,

    parse_date('%m/%d/%Y', last_week_start_date) as last_week_start_date,
    parse_date('%m/%d/%Y', last_week_end_date) as last_week_end_date,
    parse_date(
        '%m/%d/%Y', first_lesson_completion_date
    ) as first_lesson_completion_date,
    parse_date(
        '%m/%d/%Y', most_recent_lesson_completion_date
    ) as most_recent_lesson_completion_date,

    coalesce(
        student_grade.string_value, cast(student_grade.long_value as string)
    ) as student_grade,
from {{ src_model }}
