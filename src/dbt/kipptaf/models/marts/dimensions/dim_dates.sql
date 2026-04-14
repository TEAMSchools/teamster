with
    date_spine as (
        -- generate_date_array cannot produce the full 2000-9999 range in a single
        -- array call (BigQuery element limit). Cross-join year × day-of-year instead.
        select date_add(date(yr, 1, 1), interval off day) as date_value,
        from unnest(generate_array(2000, 9999)) as yr
        cross join unnest(generate_array(0, 365)) as off
        where
            off
            < if(mod(yr, 400) = 0 or (mod(yr, 4) = 0 and mod(yr, 100) != 0), 366, 365)
    )

select
    date_value as date_key,

    cast(date_value as timestamp) as date_timestamp,

    extract(dayofweek from date_value) as day_of_week,
    format_date('%A', date_value) as day_of_week_name,
    extract(day from date_value) as day_of_month,
    extract(dayofyear from date_value) as day_of_year,
    extract(isoweek from date_value) as week_of_year,
    extract(month from date_value) as month_number,
    format_date('%B', date_value) as month_name,
    extract(quarter from date_value) as quarter_number,
    extract(year from date_value) as year_number,

    extract(dayofweek from date_value) between 2 and 6 as is_weekday,

    {{
        date_to_fiscal_year(
            date_field="date_value", start_month=7, year_source="start"
        )
    }} as academic_year,

    {{ date_to_fiscal_year(date_field="date_value", start_month=7, year_source="end") }}
    as fiscal_year,

    date_trunc(date_value, week) as week_start_date,
    -- date_add can overflow for dates in the last week of 9999; cap days added
    date_add(
        date_trunc(date_value, week),
        interval least(
            6, date_diff(date(9999, 12, 31), date_trunc(date_value, week), day)
        )
        day
    ) as week_end_date,

    -- trunk-ignore(sqlfluff/LT01): week(monday) requires special formatting
    date_trunc(date_value, week(monday)) as week_start_monday,

    -- trunk-ignore(sqlfluff/LT01): week(monday) requires special formatting
    -- date_add can overflow for dates in the last week of 9999; cap days added
    date_add(
        -- trunk-ignore(sqlfluff/LT01): week(monday) requires special formatting
        date_trunc(date_value, week(monday)),
        interval least(
            6,
            date_diff(
                date(9999, 12, 31),
                -- trunk-ignore(sqlfluff/LT01): week(monday) requires special formatting
                date_trunc(date_value, week(monday)),
                day
            )
        ) day
    ) as week_end_sunday,
from date_spine
