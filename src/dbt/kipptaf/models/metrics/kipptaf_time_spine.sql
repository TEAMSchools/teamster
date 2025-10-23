with
    date_spine as (
        select date_day,
        from
            unnest(
                generate_date_array(
                    '2002-07-01', '{{ var("current_fiscal_year" ) }}-06-30'
                )
            ) as date_day
    ),

    kipptaf_date_spine as (
        select
            date_spine.date_day,
            date_trunc(date_spine.date_day, week(monday)) as week_start_monday,
            date_add(
                date_trunc(date_spine.date_day, week(monday)), interval 6 day
            ) as week_end_sunday,
            {{
                date_to_fiscal_year(
                    date_field="date_day", start_month=7, year_source="start"
                )
            }} as academic_year,
        from date_spine

    )

select *,
from kipptaf_date_spine
