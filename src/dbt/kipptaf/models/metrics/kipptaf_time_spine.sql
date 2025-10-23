-- select date_day,
-- from
-- unnest(
-- generate_date_array('2002-07-01', '{{ var("current_fiscal_year" ) }}-06-30')
-- ) as date_day
with
    date_spine as (
        select
            date_day,
            -- Calculation for week start/end
            date_trunc('week', date_day) as week_start,
            dateadd(day, 6, date_trunc('week', date_day)) as week_end,

            -- Placeholder for joining to a lookup table
            -- e.g., joined_lookup.reporting_term,
            'Term A' as reporting_term,  -- Replace with actual join logic

            -- Placeholder for academic year logic
            case
                when extract(month from date_day) >= 8
                then extract(year from date_day) + 1
                else extract(year from date_day)
            end as academic_year,

            -- Placeholder for financial quarter logic
            date_trunc('quarter', date_day) as financial_quarter  -- Or more complex logic

        from
            {{
                dbt_utils.date_spine(
                    "2002-07-01",
                    '{{ var("current_fiscal_year" ) }}-06-30',
                    'date_day'
                )
            }}
    )

select *
from date_spine
