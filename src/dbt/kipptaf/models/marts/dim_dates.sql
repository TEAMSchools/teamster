with
    timestamp_array as (
        select
            date_timestamp,

            datetime(
                date_timestamp, '{{ var("local_timezone") }}'
            ) as date_datetime_local,

            date(date_timestamp, '{{ var("local_timezone") }}') as date_local,
        from
            unnest(
                generate_timestamp_array(
                    timestamp('2002-07-01', '{{ var("local_timezone") }}'),
                    timestamp('2099-12-31', '{{ var("local_timezone") }}'),
                    interval 1 day
                )
            ) as date_timestamp
    )

select
    date_timestamp,
    date_datetime_local,
    date_local as date_day,

    date_trunc(date_local, week) as week_start_date,
    last_day(date_local, week) as week_end_date,

    -- trunk-ignore(sqlfluff/LT01)
    date_trunc(date_local, week(monday)) as week_start_monday,

    -- trunk-ignore(sqlfluff/LT01)
    last_day(date_local, week(monday)) as week_end_sunday,

    {{
        date_to_fiscal_year(
            date_field="date_local", start_month=7, year_source="start"
        )
    }} as academic_year,

    {{ date_to_fiscal_year(date_field="date_local", start_month=7, year_source="end") }}
    as fiscal_year,
from timestamp_array
