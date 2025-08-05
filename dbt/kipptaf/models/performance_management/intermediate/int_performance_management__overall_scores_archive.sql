select distinct employee_number, academic_year, final_score, final_tier,
from {{ ref("stg_performance_management__observation_details_archive") }}
