select
    worker_id,
    lastest_update,
    rn_employee_code,

    {# pivot cols #}
    taken_learning_center,
    taken_no_accrual,
    taken_please_select_pay_code,
    taken_pto,
    taken_sick,
    taken_unused_pto,
    taken_vacation,
    balance_learning_center,
    balance_no_accrual,
    balance_please_select_pay_code,
    balance_pto,
    balance_sick,
    balance_unused_pto,
    balance_vacation,
from
    {{ ref("stg_adp_workforce_manager__accrual_reporting_period_summary") }} pivot (
        max(accrual_taken_to_date_hours) as taken,
        max(accrual_available_balance_hours) as balance
        for accrual_code in (
            'Learning Center' as learning_center,
            'No Accrual' as no_accrual,
            'Please Select Pay Code' as please_select_pay_code,
            'PTO' as pto,
            'Sick' as sick,
            'Unused PTO' as unused_pto,
            'Vacation' as vacation
        )
    )
