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

    start_order as (
        select
            *,
            row_number() over (
                partition by number, effective_start order by effective_end asc
            ) as rn_employee_start,
        from parsed_dates
        where effective_start <= '2020-12-31'
    )


