with
    workers as (
        select
            associate_oid,
            effective_date_start,
            worker_dates_surrogate_key,
            worker_dates,
        from {{ ref("stg_adp_workforce_now__workers") }}
    ),

    deduplicate as (
        select
            *,

            lag(worker_dates_surrogate_key, 1, '') over (
                partition by associate_oid order by effective_date_start asc
            ) as worker_dates_surrogate_key_lag,
        from workers
    ),

    flattened as (
        select
            associate_oid,
            effective_date_start,
            worker_dates_surrogate_key,

            cast(
                worker_dates.originalhiredate as date
            ) as worker_dates__original_hire_date,
            cast(
                worker_dates.terminationdate as date
            ) as worker_dates__termination_date,
            cast(worker_dates.rehiredate as date) as worker_dates__rehire_date,
        from deduplicate
        where worker_dates_surrogate_key != worker_dates_surrogate_key_lag
    )

select
    *,

    coalesce(
        worker_dates__rehire_date, worker_dates__original_hire_date
    ) as worker_hire_date_recent,
from flattened
