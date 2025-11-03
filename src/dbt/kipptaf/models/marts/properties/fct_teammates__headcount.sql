with
    teammate_history as (
        select
            teammate_event_key,
            employee_number,
            effective_date_start,
            effective_date_end,
        from {{ ref("dim_teammates") }}
        where primary_indicator and assignment_status in ('Active', 'Leave')
    ),

    headcount_events as (
        select employee_number, effective_date_start as event_date, 1 as headcount_value
        from teammate_history

        union all

        select
            employee_number,
            date_add(effective_date_end, interval 1 day) as event_date,
            -1 as headcount_value
        from teammate_history
        where effective_date_end < '9999-12-31'
    )

select
    {{ dbt_utils.generate_surrogate_key(["employee_number", "event_date"]) }}
    as headcount_event_key,
    employee_number,
    event_date,
    headcount_value
from headcount_events
