with
    reports_to as (
        select
            rt.item_id,
            rt.effective_date_start,
            rt.reports_to_associate_oid,
            rt.reports_to_position_id,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "rt.reports_to_associate_oid",
                        "rt.reports_to_position_id",
                    ]
                )
            }} as attribute_hash,
        from
            {{ ref("int_adp_workforce_now__workers__work_assignments__reports_to") }}
            as rt
    ),

    change_detection as (
        select
            *,

            lag(attribute_hash, 1, '') over (
                partition by item_id order by effective_date_start asc
            ) as attribute_hash_lag,
        from reports_to
    ),

    change_points as (
        select
            item_id,
            effective_date_start,
            reports_to_associate_oid as manager_associate_oid,

            coalesce(
                date_sub(
                    lead(effective_date_start) over (
                        partition by item_id order by effective_date_start asc
                    ),
                    interval 1 day
                ),
                date '9999-12-31'
            ) as effective_date_end,
        from change_detection
        where attribute_hash != attribute_hash_lag
    ),

    workers as (
        {{
            dbt_utils.deduplicate(
                relation=ref("int_adp_workforce_now__workers"),
                partition_by="associate_oid",
                order_by="effective_date_start desc",
            )
        }}
    ),

    employee_numbers as (
        select employee_number, adp_associate_id,
        from {{ ref("stg_people__employee_numbers") }}
        where is_active
    )

select
    {{ dbt_utils.generate_surrogate_key(["cp.item_id", "cp.effective_date_start"]) }}
    as work_assignment_reporting_relationship_key,

    {{ dbt_utils.generate_surrogate_key(["cp.item_id"]) }} as work_assignment_key,

    if(
        mgr.employee_number is not null,
        {{ dbt_utils.generate_surrogate_key(["mgr.employee_number"]) }},
        cast(null as string)
    ) as manager_staff_key,

    cp.effective_date_start as effective_start_date,
    cp.effective_date_end as effective_end_date,

    if(cp.effective_date_end = '9999-12-31', true, false) as is_current,
from change_points as cp
left join workers as mgr_w on cp.manager_associate_oid = mgr_w.associate_oid
left join employee_numbers as mgr on mgr_w.worker_id__id_value = mgr.adp_associate_id
