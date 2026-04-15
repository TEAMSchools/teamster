with
    deduped as (
        {{
            dbt_utils.deduplicate(
                relation=ref(
                    "stg_adp_workforce_now__pension_and_benefits_enrollments"
                ),
                partition_by="employee_number, plan_type, plan_name, enrollment_start_date",
                order_by="enrollment_end_date desc",
            )
        }}
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "employee_number",
                "plan_type",
                "plan_name",
                "enrollment_start_date",
            ]
        )
    }} as staff_benefits_enrollment_key,

    {{ dbt_utils.generate_surrogate_key(["employee_number"]) }} as staff_key,

    employee_number,
    plan_type,
    plan_name,
    coverage_level,
    enrollment_status,

    enrollment_start_date,
    enrollment_end_date,
from deduped
where employee_number is not null
