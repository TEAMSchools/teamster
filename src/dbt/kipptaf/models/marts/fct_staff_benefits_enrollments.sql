select
    coverage_level,
    effective_date,
    employee_number,
    enrollment_end_date,
    enrollment_start_date,
    enrollment_status,
    plan_name,
    plan_type,
    position_id,
    rn_enrollment_recent,
from {{ ref("stg_adp_workforce_now__pension_and_benefits_enrollments") }}
