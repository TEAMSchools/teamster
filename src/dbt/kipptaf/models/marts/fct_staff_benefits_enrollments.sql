select
    coverage_level,
    cast(effective_date as timestamp) as effective_date,
    employee_number,
    cast(enrollment_end_date as timestamp) as enrollment_end_date,
    cast(enrollment_start_date as timestamp) as enrollment_start_date,
    enrollment_status,
    plan_name,
    plan_type,
    position_id,
    rn_enrollment_recent,

    {{
        dbt_utils.generate_surrogate_key(
            ["employee_number", "plan_type", "enrollment_start_date"]
        )
    }} as staff_benefits_enrollments_key,
from {{ ref("stg_adp_workforce_now__pension_and_benefits_enrollments") }}
