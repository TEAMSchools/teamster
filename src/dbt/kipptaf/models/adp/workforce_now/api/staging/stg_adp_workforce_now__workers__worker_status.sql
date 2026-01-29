with
    workers as (
        select
            associate_oid,
            effective_date_start,
            worker_status_surrogate_key,
            worker_status,
        from {{ ref("stg_adp_workforce_now__workers") }}
    ),

    deduplicate as (
        select
            *,

            lag(worker_status_surrogate_key, 1, '') over (
                partition by associate_oid order by effective_date_start asc
            ) as worker_status_surrogate_key_lag,
        from workers
    )

select
    associate_oid,
    effective_date_start,
    worker_status_surrogate_key,

    worker_status.statuscode.codevalue as worker_status__status_code__code_value,
    worker_status.statuscode.longname as worker_status__status_code__long_name,
    worker_status.statuscode.shortname as worker_status__status_code__short_name,

    cast(
        worker_status.statuscode.effectivedate as date
    ) as worker_status__status_code__effective_date,

    lag(worker_status.statuscode.codevalue, 1) over (
        partition by associate_oid order by effective_date_start asc
    ) as worker_status__status_code__code_value_lag,
from deduplicate
where worker_status_surrogate_key != worker_status_surrogate_key_lag
