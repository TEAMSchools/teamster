{%- set end_date = (
    "cast('" + var("current_fiscal_year") | string + "-06-30' as date)"
) -%}

{{-
    dbt_utils.date_spine(
        start_date="cast('2002-07-01' as date)",
        end_date=end_date,
        datepart="day",
    )
-}}
