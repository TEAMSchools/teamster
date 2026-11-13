select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "employee_number",
                "position_id",
                "plan_type",
                "plan_name",
                "enrollment_start_date",
            ]
        )
    }} as staff_benefits_enrollment_key,

    {{ dbt_utils.generate_surrogate_key(["employee_number"]) }} as staff_key,

    plan_type,
    plan_name,
    coverage_level,

    enrollment_start_date as start_date,
    enrollment_end_date as end_date,
from {{ ref("stg_adp_workforce_now__pension_and_benefits_enrollments") }}
where employee_number is not null
