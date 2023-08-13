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
                "client_date",
                "sync_date",
                "assessing_teacher_staff_id",
                "assessment_grade",
            ],
        )
    }},
    safe_cast(assessing_teacher_staff_id as string) as assessing_teacher_staff_id,
    safe_cast(assessment_grade as string) as assessment_grade,
    safe_cast(client_date as date) as client_date,
    safe_cast(sync_date as date) as sync_date,
    safe_cast(left(school_year, 4) as int) as academic_year,
from {{ src_pss }}
