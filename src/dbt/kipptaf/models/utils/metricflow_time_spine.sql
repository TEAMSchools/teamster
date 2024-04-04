{{ config(materialized="table") }}

with
    date_spine as (
        {{ dbt.date_spine("day", "date(2000, 01, 01)", "date(2030, 01, 01)") }}
    ),

    final as (select cast(date_day as date) as date_day, from date_spine)

select *,
from final
