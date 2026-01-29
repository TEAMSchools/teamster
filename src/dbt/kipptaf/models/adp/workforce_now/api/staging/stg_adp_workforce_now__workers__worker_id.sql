with
    workers as (
        select associate_oid, effective_date_start, worker_id_surrogate_key, worker_id,
        from {{ ref("stg_adp_workforce_now__workers") }}
    ),

    deduplicate as (
        select
            *,

            lag(worker_id_surrogate_key, 1, '') over (
                partition by associate_oid order by effective_date_start asc
            ) as worker_id_surrogate_key_lag,
        from workers
    )

select
    associate_oid,
    effective_date_start,
    worker_id_surrogate_key,

    worker_id.idvalue as worker_id__id_value,

    worker_id.schemecode.codevalue as worker_id__scheme_code__code_value,
    worker_id.schemecode.longname as worker_id__scheme_code__long_name,
    worker_id.schemecode.shortname as worker_id__scheme_code__short_name,

    cast(
        worker_id.schemecode.effectivedate as date
    ) as worker_id__scheme_code__effective_date,
from deduplicate
where worker_id_surrogate_key != worker_id_surrogate_key_lag
