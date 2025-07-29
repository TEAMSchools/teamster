with
    additional_earnings_report as (
        select
            * except (employee_number, file_number_pay_statements, gross_pay, pay_date),

            cast(employee_number as int) as employee_number,
            cast(file_number_pay_statements as int) as file_number_pay_statements,

            cast(regexp_replace(gross_pay, r'[^\d\.-]', '') as numeric) as gross_pay,

            concat(payroll_company_code, file_number_pay_statements) as position_id,

            parse_date('%m/%d/%Y', pay_date) as pay_date,
        from
            {{
                source(
                    "adp_workforce_now",
                    "src_adp_workforce_now__additional_earnings_report",
                )
            }}
        where additional_earnings_description not in ('Sick', 'C-SICK')
    )

select
    *,

    {{ date_to_fiscal_year(date_field="pay_date", start_month=7, year_source="start") }}
    as academic_year,
from additional_earnings_report
