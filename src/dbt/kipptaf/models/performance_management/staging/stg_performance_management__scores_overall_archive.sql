select
    employee_number,
    academic_year,
    pm_term as form_term,
    etr_score,
    so_score,
    overall_score,

    'Coaching Tool: Coach ETR and Reflection' as form_long_name,

    concat(pm_term, ' (Coach)') as form_short_name,
from
    {{
        source(
            "performance_management",
            "src_performance_management__scores_overall_archive",
        )
    }}
