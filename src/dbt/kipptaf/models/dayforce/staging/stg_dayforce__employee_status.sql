with
    parsed_dates as (
        select
            number,
            status,
            status_reason_description,
            base_salary,
            extract(
                date
                from
                    parse_timestamp(
                        '%Y-%m-%dT%H:%M:%S%Ez', effective_start
                    ) at time zone 'America/New_York'
            ) as effective_start,
            coalesce(
                extract(
                    date
                    from
                        parse_timestamp(
                            '%Y-%m-%dT%H:%M:%S%Ez', effective_end
                        ) at time zone 'America/New_York'
                ),
                '2020-12-31'
            ) as effective_end,
        from {{ source("dayforce", "src_dayforce__employee_status") }}
    ),

    with_prev as (
        select
            *,
            lag(effective_end, 1) over (
                partition by number order by effective_end asc
            ) as effective_end_prev,
        from parsed_dates
    )

select
    number as employee_number,
    status,
    status_reason_description,
    base_salary,
    effective_end as status_effective_end_date,
    if(
        effective_start = effective_end_prev,
        date_add(effective_start, interval 1 day),
        effective_start
    ) as status_effective_start_date,
from with_prev
where effective_start <= '2020-12-31'
