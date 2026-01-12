{{
    dbt_utils.deduplicate(
        relation=ref("stg_adp_workforce_now__additional_earnings_report"),
        partition_by="employee_number, academic_year, pay_date,additional_earnings_description, gross_pay",
        order_by="pay_date",
    )
}}
