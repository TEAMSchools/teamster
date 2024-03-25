{% set src_aer = source(
    "adp_workforce_now", "src_adp_workforce_now__additional_earnings_report"
) %}

with
    additional_earnings_report as (
        select
            {{ dbt_utils.star(from=src_aer, except=["pay_date", "gross_pay"]) }},
            parse_date('%m/%d/%Y', pay_date) as pay_date,
            cast(regexp_replace(gross_pay, r'[^\d\.-]', '') as numeric) as gross_pay,
            concat(payroll_company_code, file_number_pay_statements) as position_id,
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
