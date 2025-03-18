select
    subject_employee_number as employee_number,
    academic_year,
    pm_term as form_term,
    score_type,
    observer_employee_number,
    measurement_name,
    score_value as row_score_value,

    safe_cast(null as string) as observer_name,
    safe_cast(observed_at as date) as observed_at,
from
    {{
        source(
            "performance_management",
            "src_performance_management__scores_detail_archive",
        )
    }}
