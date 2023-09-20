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
    )

select
    number as employee_number,
    status,
    status_reason_description,
    base_salary,
    effective_end as status_effective_end,
    coalesce(
        date_add(
            lag(effective_end, 1) over (
                partition by number, effective_start order by effective_end asc
            ),
            interval 1 day
        ),
        effective_start
    ) as status_effective_start,
from parsed_dates
where effective_end > effective_start and effective_start <= '2020-12-31'
