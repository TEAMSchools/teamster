with
    work_assignment_history as (
        select
            * except (
                _fivetran_start,
                _fivetran_end,
                _fivetran_synced,
                assignment_status_reason,
                home_work_location_name,
                worker_type
            ),

            extract(date from _fivetran_start) as _fivetran_start_date,
            extract(date from _fivetran_end) as _fivetran_end_date,

            coalesce(
                assignment_status_reason_long_name, assignment_status_reason_short_name
            ) as assignment_status_reason,
            coalesce(
                home_work_location_name_long_name, home_work_location_name_short_name
            ) as home_work_location_name,
            coalesce(worker_type_long_name, worker_type_short_name) as worker_type,

            timestamp(
                datetime(_fivetran_start), '{{ var("local_timezone") }}'
            ) as _fivetran_start,

            coalesce(
                safe.timestamp(datetime(_fivetran_end), '{{ var("local_timezone") }}'),
                timestamp('9999-12-31 23:59:59.999999')
            ) as _fivetran_end,

            lag(assignment_status_long_name, 1) over (
                partition by worker_id order by assignment_status_effective_date asc
            ) as assignment_status_long_name_lag,
        from {{ source("adp_workforce_now", "work_assignment_history") }}
    )

select
    *,

    if(
        hire_date > current_date('{{ var("local_timezone") }}')
        and assignment_status_long_name = 'Active'
        and (
            assignment_status_long_name_lag = 'Terminated'
            or assignment_status_long_name_lag is null
        ),
        true,
        false
    ) as is_prestart,
from work_assignment_history
