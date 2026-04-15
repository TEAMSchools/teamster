with
    workers as (
        select
            w.associate_oid,
            w.effective_date_start,
            w.worker_status__status_code__code_value,
            w.worker_status__status_code__long_name,
            w.worker_status__status_code__short_name,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "w.worker_status__status_code__code_value",
                    ]
                )
            }} as attribute_hash,
        from {{ ref("stg_adp_workforce_now__workers") }} as w
    ),

    change_detection as (
        select
            *,

            lag(attribute_hash, 1, '') over (
                partition by associate_oid order by effective_date_start asc
            ) as attribute_hash_lag,
        from workers
    ),

    change_points as (
        select
            associate_oid,
            effective_date_start,
            worker_status__status_code__code_value as status_code,

            coalesce(
                worker_status__status_code__long_name,
                worker_status__status_code__short_name
            ) as status_name,

            coalesce(
                date_sub(
                    lead(effective_date_start) over (
                        partition by associate_oid order by effective_date_start asc
                    ),
                    interval 1 day
                ),
                date '9999-12-31'
            ) as effective_date_end,
        from change_detection
        where attribute_hash != attribute_hash_lag
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["en.employee_number", "cp.effective_date_start"]
        )
    }} as staff_status_key,

    {{ dbt_utils.generate_surrogate_key(["en.employee_number"]) }} as staff_key,

    cp.status_code,
    cp.status_name,
    cp.effective_date_start,
    cp.effective_date_end,

    if(cp.effective_date_end = '9999-12-31', true, false) as is_current_record,
from change_points as cp
inner join
    {{ ref("stg_people__employee_numbers") }} as en
    on cp.associate_oid = en.adp_associate_id
    and en.is_active
