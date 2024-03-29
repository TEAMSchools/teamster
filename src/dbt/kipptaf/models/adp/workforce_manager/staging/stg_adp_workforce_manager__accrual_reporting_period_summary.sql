select
    employee_name_id,
    accrual_code,
    accrual_reporting_period,
    accrual_opening_vested_balance_hours,
    accrual_earned_to_date_hours,
    accrual_taken_to_date_hours,
    accrual_available_balance_hours,
    accrual_planned_takings_hours,
    accrual_pending_grants_hours,
    accrual_ending_vested_balance_hours,
    _dagster_partition_date as lastest_update,
    regexp_extract(employee_name_id, r'\((\w+)\)') as worker_id,

    row_number() over (
        partition by employee_name_id, accrual_code
        order by _dagster_partition_date desc
    ) as rn_employee_code,
from
    {{
        source(
            "adp_workforce_manager",
            "src_adp_workforce_manager__accrual_reporting_period_summary",
        )
    }}
