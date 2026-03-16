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
from {{ ref("stg_adp_workforce_now__pension_and_benefits_enrollments") }}
