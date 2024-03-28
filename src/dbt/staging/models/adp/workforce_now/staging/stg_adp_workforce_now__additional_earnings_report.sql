{% set src_aer = source(
    "adp_workforce_now", "src_adp_workforce_now__additional_earnings_report"
) %}

with
    additional_earnings_report as (
        select
            {{
                dbt_utils.star(
                    from=src_aer,
                    except=["pay_date", "gross_pay", "check_voucher_number"],
                )
            }},

            parse_date('%m/%d/%Y', pay_date) as pay_date,
            concat(payroll_company_code, file_number_pay_statements) as position_id,
            coalesce(
                safe_cast(check_voucher_number.long_value as string),
                check_voucher_number.string_value
            ) as check_voucher_number,
            safe_cast(
                regexp_replace(gross_pay, r'[^\d\.-]', '') as numeric
            ) as gross_pay,
        from {{ src_aer }}
        where additional_earnings_description not in ('Sick', 'C-SICK')
    )

select
    *,
    {{
        teamster_utils.date_to_fiscal_year(
            date_field="pay_date", start_month=7, year_source="start"
        )
    }} as academic_year,
from additional_earnings_report
