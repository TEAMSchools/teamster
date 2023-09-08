{% set src_pss = source("amplify", "src_amplify__pm_student_summary") %}

select
    {{
        dbt_utils.generate_surrogate_key(
            ["student_primary_id", "school_year", "pm_period"]
        )
    }} as surrogate_key,
    {{
        dbt_utils.star(
            from=src_pss,
            except=[
                "assessing_teacher_staff_id",
                "assessment_grade",
                "client_date",
                "enrollment_grade",
                "official_teacher_staff_id",
                "score_change",
                "score",
                "sync_date",
            ],
        )
    }},

    safe_cast(client_date as date) as client_date,
    safe_cast(sync_date as date) as sync_date,

    coalesce(
        official_teacher_staff_id.string_value,
        safe_cast(official_teacher_staff_id.long_value as string)
    ) as official_teacher_staff_id,
    coalesce(
        assessing_teacher_staff_id.string_value,
        safe_cast(assessing_teacher_staff_id.double_value as string)
    ) as assessing_teacher_staff_id,
    coalesce(
        assessment_grade.string_value, safe_cast(assessment_grade.long_value as string)
    ) as assessment_grade,
    coalesce(
        enrollment_grade.string_value, safe_cast(enrollment_grade.long_value as string)
    ) as enrollment_grade,
    coalesce(
        safe_cast(score.double_value as numeric), safe_cast(score.long_value as numeric)
    ) as score,
    coalesce(
        safe_cast(score_change.double_value as numeric),
        safe_cast(score_change.string_value as numeric)
    ) as score_change,

    safe_cast(left(school_year, 4) as int) as academic_year,
from {{ src_pss }}
