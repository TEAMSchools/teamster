with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=ref("stg_adp_workforce_now__additional_earnings_report"),
                partition_by="employee_number, academic_year, pay_date,additional_earnings_description, gross_pay",
                order_by="pay_date",
            )
        }}
    )

select
    academic_year,
    additional_earnings_code,
    additional_earnings_description,
    check_voucher_number,
    cost_number,
    cost_number_description,
    employee_number,
    file_number_pay_statements,
    gross_pay,
    pay_date,
    payroll_company_code,
    position_id,
    position_status,
from deduplicate
