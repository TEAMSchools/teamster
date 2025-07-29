-- {{ 
-- config(
-- materialized = 'table'
-- ) 
-- }}
with
    days as (
        {{
            dbt_utils.date_spine(
                datepart="day",
                start_date="DATE('2000-01-01')",
                end_date="DATE('2027-01-01')",
            )
        }}
    ),

select *
from days
